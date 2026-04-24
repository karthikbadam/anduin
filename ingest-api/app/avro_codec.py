"""Confluent wire-format Avro codec.

Format: `\x00` magic byte + big-endian 4-byte schema id + Avro binary body.
Schemas are fetched from Schema Registry at startup and cached together in a
`named_schemas` dict so references (Envelope, GeoPoint) resolve cross-subject.
"""
from __future__ import annotations

import io
import json
import struct
from dataclasses import dataclass

import httpx
from fastavro import parse_schema, schemaless_reader, schemaless_writer

MAGIC_BYTE = b"\x00"


@dataclass
class RegisteredSchema:
    schema_id: int
    parsed: dict  # fastavro-parsed schema


class AvroCodec:
    """Holds schema-id + parsed-schema pairs keyed by subject, plus a shared
    named_schemas cache so reference resolution works across subjects."""

    def __init__(self, registry_url: str):
        self.registry_url = registry_url.rstrip("/")
        self._named: dict[str, dict] = {}
        self._by_subject: dict[str, RegisteredSchema] = {}

    async def load(self, subjects: list[str]) -> None:
        """Fetch latest version of each subject and parse into named_schemas."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            # First pass: fetch all schemas and their refs recursively.
            cache: dict[str, dict] = {}
            for subject in subjects:
                await self._fetch_with_refs(client, subject, cache)

            # Second pass: parse in dependency order using the shared named_schemas.
            # fastavro handles ordering as long as all referenced types appear
            # somewhere in named_schemas when parse_schema is called.
            for subject, payload in cache.items():
                schema_dict = json.loads(payload["schema"])
                parsed = parse_schema(schema_dict, named_schemas=self._named)
                self._by_subject[subject] = RegisteredSchema(
                    schema_id=payload["id"], parsed=parsed
                )

    async def _fetch_with_refs(
        self, client: httpx.AsyncClient, subject: str, cache: dict[str, dict]
    ) -> None:
        if subject in cache:
            return
        r = await client.get(
            f"{self.registry_url}/subjects/{subject}/versions/latest"
        )
        r.raise_for_status()
        payload = r.json()  # {id, version, subject, schema, references?}
        for ref in payload.get("references", []):
            await self._fetch_with_refs(client, ref["subject"], cache)
        cache[subject] = payload

    def encode(self, subject: str, value: dict) -> bytes:
        rs = self._by_subject[subject]
        buf = io.BytesIO()
        buf.write(MAGIC_BYTE)
        buf.write(struct.pack(">I", rs.schema_id))
        schemaless_writer(buf, rs.parsed, value)
        return buf.getvalue()

    def decode(self, subject: str, data: bytes) -> dict:
        if not data or data[0:1] != MAGIC_BYTE:
            raise ValueError("missing Confluent magic byte")
        schema_id = struct.unpack(">I", data[1:5])[0]
        rs = self._by_subject[subject]
        if rs.schema_id != schema_id:
            # For Stage 1 we only round-trip our own writes; future versions
            # should fetch the writer's schema by id for reader/writer resolution.
            raise ValueError(
                f"schema id mismatch: wrote {schema_id}, have {rs.schema_id}"
            )
        return schemaless_reader(io.BytesIO(data[5:]), rs.parsed)

    def schema_id(self, subject: str) -> int:
        return self._by_subject[subject].schema_id
