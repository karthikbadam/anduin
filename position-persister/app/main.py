"""Position persister.

- Single aiokafka consumer on `anduin.satellite.position.v1`.
- fastavro decodes Confluent wire format → dict.
- Batches into Postgres (500 rows OR 500 ms, whichever first).
- Writes Redis hot state (ZSET `sats:active` scored by last-seen ms;
  list `sats:track:{norad_id}` capped at 120 recent samples).
- Upserts `satellites` on first-seen NORAD id.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
from contextlib import suppress
from datetime import datetime, timezone
from typing import Any

import asyncpg
import redis.asyncio as redis_asyncio
from aiokafka import AIOKafkaConsumer

from .codec import SchemaCache

log = logging.getLogger("position-persister")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

TOPIC = "anduin.satellite.position.v1"
GROUP = "anduin.position-persister"
FLUSH_ROWS = 500
FLUSH_INTERVAL_S = 0.5
TRACK_LIST_MAX = 120  # last ~10 minutes at 5s cadence


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


async def run() -> None:
    dsn = _env("POSTGRES_DSN", "postgresql://anduin:anduin-dev@postgres:5432/anduin")
    bootstrap = _env("KAFKA_BOOTSTRAP", "kafka:29092")
    registry = _env("SCHEMA_REGISTRY_URL", "http://schema-registry:8081")
    redis_url = _env("REDIS_URL", "redis://redis:6379/0")

    pool = await asyncpg.create_pool(dsn, min_size=2, max_size=5)
    redis = redis_asyncio.from_url(redis_url, decode_responses=True)
    cache = SchemaCache(registry)

    consumer = AIOKafkaConsumer(
        TOPIC,
        bootstrap_servers=bootstrap,
        group_id=GROUP,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        value_deserializer=None,
    )
    await consumer.start()
    log.info("started: topic=%s group=%s", TOPIC, GROUP)

    buffer: list[dict[str, Any]] = []
    last_flush = asyncio.get_event_loop().time()
    stop_event = asyncio.Event()

    def _stop() -> None:
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        with suppress(NotImplementedError):
            asyncio.get_event_loop().add_signal_handler(sig, _stop)

    async def flush() -> None:
        nonlocal buffer, last_flush
        if not buffer:
            last_flush = asyncio.get_event_loop().time()
            return
        rows = buffer
        buffer = []
        # Postgres insert (ignore conflicts).
        async with pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO satellite_positions
                  (norad_id, sampled_at, lat_deg, lon_deg, alt_km, speed_km_s,
                   healpix_cell, tle_epoch, tle_source)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                ON CONFLICT (norad_id, sampled_at) DO NOTHING
                """,
                [
                    (
                        r["norad_id"], r["sampled_at"], r["lat_deg"], r["lon_deg"],
                        r["alt_km"], r["speed_km_s"], r["healpix_cell"],
                        r["tle_epoch"], r["tle_source"],
                    )
                    for r in rows
                ],
            )
            # Upsert unseen NORAD IDs into satellites table.
            await conn.executemany(
                """
                INSERT INTO satellites (norad_id, name, last_tle_epoch, updated_at)
                VALUES ($1, $2, $3, now())
                ON CONFLICT (norad_id) DO UPDATE SET
                  name = COALESCE(EXCLUDED.name, satellites.name),
                  last_tle_epoch = GREATEST(
                    satellites.last_tle_epoch, EXCLUDED.last_tle_epoch
                  ),
                  updated_at = now()
                """,
                [(r["norad_id"], r.get("name"), r["tle_epoch"]) for r in rows],
            )

        # Redis hot state: ZSET + per-sat list.
        pipe = redis.pipeline()
        for r in rows:
            score_ms = int(r["sampled_at"].timestamp() * 1000)
            pipe.zadd("sats:active", {r["norad_id"]: score_ms})
            track = json.dumps(
                {
                    "t": score_ms,
                    "lat": r["lat_deg"], "lon": r["lon_deg"], "alt": r["alt_km"],
                    "v": r["speed_km_s"], "cell": r["healpix_cell"],
                }
            )
            pipe.lpush(f"sats:track:{r['norad_id']}", track)
            pipe.ltrim(f"sats:track:{r['norad_id']}", 0, TRACK_LIST_MAX - 1)
        await pipe.execute()

        # Only commit Kafka offsets after DB + Redis succeed.
        await consumer.commit()
        log.info("flushed %d rows", len(rows))
        last_flush = asyncio.get_event_loop().time()

    try:
        while not stop_event.is_set():
            # Drain up to FLUSH_ROWS or FLUSH_INTERVAL_S.
            batch = await consumer.getmany(
                timeout_ms=int(FLUSH_INTERVAL_S * 1000), max_records=FLUSH_ROWS
            )
            for _tp, messages in batch.items():
                for msg in messages:
                    try:
                        _sid, decoded = await cache.decode(msg.value)
                    except Exception as e:  # noqa: BLE001
                        log.warning("decode error offset=%d: %s", msg.offset, e)
                        continue
                    pos = decoded["position"]
                    buffer.append(
                        {
                            "norad_id": decoded["norad_id"],
                            "name": decoded.get("name"),
                            "sampled_at": _to_dt(decoded["sampled_at"]),
                            "lat_deg": pos["lat_deg"],
                            "lon_deg": pos["lon_deg"],
                            "alt_km": pos["alt_km"],
                            "speed_km_s": decoded["speed_km_s"],
                            "healpix_cell": decoded["healpix_cell"],
                            "tle_epoch": _to_dt(decoded["tle_epoch"]),
                            "tle_source": decoded.get("tle_source", "unknown"),
                        }
                    )
            now = asyncio.get_event_loop().time()
            if len(buffer) >= FLUSH_ROWS or (now - last_flush) >= FLUSH_INTERVAL_S:
                await flush()
    finally:
        log.info("shutting down")
        await flush()
        await consumer.stop()
        await pool.close()
        await redis.aclose()


def _to_dt(v: Any) -> datetime:
    """fastavro gives us timezone-aware datetime for timestamp-millis; pass through."""
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    # Defensive: handle integer ms.
    return datetime.fromtimestamp(v / 1000, tz=timezone.utc)


if __name__ == "__main__":
    asyncio.run(run())
