"""Minimal Confluent wire-format Avro decoder used by consumer services."""
from __future__ import annotations

import io
import json
import struct

import httpx
from fastavro import parse_schema, schemaless_reader

MAGIC = b"\x00"


class SchemaCache:
    """Lazy fetch of writer schemas by id. Once parsed we keep a shared
    named_schemas dict so references (Envelope, GeoPoint) resolve."""

    def __init__(self, registry_url: str):
        self.registry = registry_url.rstrip("/")
        self._named: dict[str, dict] = {}
        self._by_id: dict[int, dict] = {}

    async def fetch(self, schema_id: int) -> dict:
        if schema_id in self._by_id:
            return self._by_id[schema_id]
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{self.registry}/schemas/ids/{schema_id}")
            r.raise_for_status()
            body = r.json()
            # references are returned as full refs; resolve each so named types are present.
            for ref in body.get("references", []):
                r2 = await client.get(
                    f"{self.registry}/subjects/{ref['subject']}/versions/{ref['version']}"
                )
                r2.raise_for_status()
                parse_schema(json.loads(r2.json()["schema"]), named_schemas=self._named)
            parsed = parse_schema(json.loads(body["schema"]), named_schemas=self._named)
            self._by_id[schema_id] = parsed
            return parsed

    async def decode(self, data: bytes) -> tuple[int, dict]:
        if not data or data[:1] != MAGIC:
            raise ValueError("missing magic byte")
        schema_id = struct.unpack(">I", data[1:5])[0]
        parsed = await self.fetch(schema_id)
        return schema_id, schemaless_reader(io.BytesIO(data[5:]), parsed)
