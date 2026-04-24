"""Produce pass events directly to Kafka (Confluent wire format).

pass-worker is internal, so it bypasses ingest-api's validation layer — the
geometry is already computed here. We serialize with fastavro against the
registered anduin.satellite.pass.v1-value schema.
"""
from __future__ import annotations

import io
import json
import logging
import os
import struct
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from confluent_kafka import Producer
from fastavro import parse_schema, schemaless_writer

log = logging.getLogger(__name__)

MAGIC = b"\x00"
TOPIC = "anduin.satellite.pass.v1"
SUBJECT = f"{TOPIC}-value"


@dataclass
class _Schema:
    schema_id: int
    parsed: dict


async def _load_schema(registry: str) -> _Schema:
    """Fetch the latest pass schema + its references from Schema Registry."""
    named: dict = {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(f"{registry}/subjects/{SUBJECT}/versions/latest")
        r.raise_for_status()
        body = r.json()
        for ref in body.get("references", []):
            r2 = await client.get(f"{registry}/subjects/{ref['subject']}/versions/{ref['version']}")
            r2.raise_for_status()
            parse_schema(json.loads(r2.json()["schema"]), named_schemas=named)
        parsed = parse_schema(json.loads(body["schema"]), named_schemas=named)
    return _Schema(schema_id=body["id"], parsed=parsed)


class PassPublisher:
    def __init__(self) -> None:
        bootstrap = os.environ.get("KAFKA_BOOTSTRAP", "kafka:29092")
        self.producer = Producer({
            "bootstrap.servers": bootstrap,
            "acks": "all",
            "enable.idempotence": True,
            "linger.ms": 10,
            "compression.type": "zstd",
        })
        self._schema: _Schema | None = None

    async def start(self, registry_url: str) -> None:
        self._schema = await _load_schema(registry_url)
        log.info("pass schema id=%d loaded", self._schema.schema_id)

    def _encode(self, value: dict) -> bytes:
        assert self._schema is not None
        buf = io.BytesIO()
        buf.write(MAGIC)
        buf.write(struct.pack(">I", self._schema.schema_id))
        schemaless_writer(buf, self._schema.parsed, value)
        return buf.getvalue()

    def publish(
        self,
        *,
        norad_id: str,
        name: str | None,
        observer_id: str,
        observer_lat: float,
        observer_lon: float,
        observer_alt_km: float,
        event_kind: str,
        event_time: datetime,
        elevation_deg: float,
        azimuth_deg: float,
        range_km: float,
    ) -> None:
        now = datetime.now(tz=timezone.utc)
        value = {
            "envelope": {
                "event_id": str(uuid.uuid4()),
                "event_version": 1,
                "occurred_at": event_time,
                "ingested_at": now,
                "source": "pass_worker",
                "trace_id": None,
            },
            "norad_id": norad_id,
            "name": name,
            "observer_id": observer_id,
            "observer": {
                "lat_deg": observer_lat,
                "lon_deg": observer_lon,
                "alt_km": observer_alt_km,
            },
            "event_kind": event_kind,
            "event_time": event_time,
            "elevation_deg": elevation_deg,
            "azimuth_deg": azimuth_deg,
            "range_km": range_km,
            "visible": None,
        }
        payload = self._encode(value)
        self.producer.produce(
            topic=TOPIC, key=f"{norad_id}|{observer_id}".encode(), value=payload
        )
        self.producer.poll(0)

    def flush(self, timeout: float = 5.0) -> int:
        return self.producer.flush(timeout)

    async def aclose(self) -> None:
        self.flush(5.0)
