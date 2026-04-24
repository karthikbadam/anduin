"""Pass worker.

- aiokafka consumer on anduin.satellite.position.v1.
- Per (norad_id, observer_id) in-memory state of the last elevation sample.
- Every position sample → compute elevation vs each registered observer →
  detect threshold crossings → POST pass events to ingest-api.
- Observers refreshed from Redis every OBSERVER_REFRESH_S.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import time
import uuid
from contextlib import suppress
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as redis_asyncio
from aiokafka import AIOKafkaConsumer

from .codec import SchemaCache
from .geometry import ObserverGeo, SatelliteGeo, compute
from .observers import Observer, load_all
from .passes import PassState, Sample, detect
from .publisher import PassPublisher

log = logging.getLogger("pass-worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

TOPIC = "anduin.satellite.position.v1"
STUB = os.environ.get("STUB_PROPAGATE", "true").lower() == "true"
OBSERVER_REFRESH_S = 10.0


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _to_dt(v: Any) -> datetime:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    return datetime.fromtimestamp(v / 1000, tz=timezone.utc)


async def run() -> None:
    bootstrap = _env("KAFKA_BOOTSTRAP", "kafka:29092")
    registry = _env("SCHEMA_REGISTRY_URL", "http://schema-registry:8081")
    redis_url = _env("REDIS_URL", "redis://redis:6379/0")

    redis = redis_asyncio.from_url(redis_url, decode_responses=True)
    cache = SchemaCache(registry)
    publisher = PassPublisher()
    await publisher.start(registry)

    # Ephemeral consumer group — we want live events, not durable progress.
    group = f"anduin.pass-worker.{uuid.uuid4().hex[:8]}"
    consumer = AIOKafkaConsumer(
        TOPIC,
        bootstrap_servers=bootstrap,
        group_id=group,
        auto_offset_reset="latest",
        enable_auto_commit=False,
        value_deserializer=None,
    )
    await consumer.start()
    log.info("pass-worker start: stub=%s group=%s", STUB, group)

    # State: (norad_id, observer_id) → (PassState, last_sample).
    state: dict[tuple[str, str], tuple[PassState, Sample | None]] = {}
    observers: list[Observer] = []
    last_observer_refresh = 0.0

    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with suppress(NotImplementedError):
            asyncio.get_event_loop().add_signal_handler(sig, stop.set)

    async def refresh_observers_if_due() -> None:
        nonlocal observers, last_observer_refresh
        if time.time() - last_observer_refresh < OBSERVER_REFRESH_S:
            return
        observers = await load_all(redis)
        last_observer_refresh = time.time()
        log.info("observers refreshed: %d active", len(observers))

    try:
        async for msg in consumer:
            if stop.is_set():
                break
            await refresh_observers_if_due()
            if not observers:
                continue

            try:
                _sid, decoded = await cache.decode(msg.value)
            except Exception as e:  # noqa: BLE001
                log.warning("decode error: %s", e)
                continue
            pos = decoded.get("position") or {}
            sat = SatelliteGeo(
                lat_deg=pos.get("lat_deg", 0.0),
                lon_deg=pos.get("lon_deg", 0.0),
                alt_km=pos.get("alt_km", 0.0),
            )
            sampled_at = _to_dt(decoded.get("sampled_at"))
            norad_id = decoded.get("norad_id", "")
            name = decoded.get("name")

            for obs in observers:
                obs_geo = ObserverGeo(obs.lat_deg, obs.lon_deg, obs.alt_km)
                angles = compute(obs_geo, sat, stub=STUB)
                sample = Sample(elev_deg=angles.elevation_deg, t_utc=sampled_at)
                key = (norad_id, obs.observer_id)
                ps, prev = state.get(key, (PassState(), None))
                evt = detect(prev, sample, ps, stub=STUB)
                state[key] = (ps, sample)
                if evt:
                    publisher.publish(
                        norad_id=norad_id,
                        name=name,
                        observer_id=obs.observer_id,
                        observer_lat=obs.lat_deg,
                        observer_lon=obs.lon_deg,
                        observer_alt_km=obs.alt_km,
                        event_kind=evt.kind,
                        event_time=evt.t_utc,
                        elevation_deg=angles.elevation_deg,
                        azimuth_deg=angles.azimuth_deg,
                        range_km=angles.range_km,
                    )
    finally:
        await consumer.stop()
        await publisher.aclose()
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(run())
