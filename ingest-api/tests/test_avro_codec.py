"""Round-trip: encode then decode via the Confluent wire format."""
from __future__ import annotations

import io
import json
import struct
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastavro import parse_schema, schemaless_reader

from app.avro_codec import MAGIC_BYTE, AvroCodec

SCHEMAS_DIR = Path(__file__).parents[2] / "schemas"


def _load_json(p: Path) -> dict:
    return json.loads(p.read_text())


@pytest.fixture()
def codec() -> AvroCodec:
    # Build a codec manually without hitting the registry — assign schema ids.
    c = AvroCodec(registry_url="http://unused")
    named: dict = {}
    # Order matters for parse_schema references.
    parse_schema(_load_json(SCHEMAS_DIR / "common" / "geo_point.avsc"), named_schemas=named)
    parse_schema(_load_json(SCHEMAS_DIR / "common" / "envelope.avsc"), named_schemas=named)
    position = parse_schema(
        _load_json(SCHEMAS_DIR / "satellite" / "satellite_position_sampled.avsc"),
        named_schemas=named,
    )
    from app.avro_codec import RegisteredSchema
    c._named = named
    c._by_subject["anduin.satellite.position.v1-value"] = RegisteredSchema(
        schema_id=42, parsed=position
    )
    return c


def test_confluent_wire_format_has_magic_and_id(codec: AvroCodec) -> None:
    now = datetime.now(tz=timezone.utc)
    value = {
        "envelope": {
            "event_id": "11111111-1111-1111-1111-111111111111",
            "event_version": 1,
            "occurred_at": now,
            "ingested_at": now,
            "source": "tle_producer",
            "trace_id": None,
        },
        "norad_id": "25544",
        "name": "ISS",
        "position": {"lat_deg": 0.0, "lon_deg": 0.0, "alt_km": 420.0},
        "speed_km_s": 7.66,
        "healpix_cell": 0,
        "tle_epoch": now,
        "sampled_at": now,
        "tle_source": "fixture",
    }
    data = codec.encode("anduin.satellite.position.v1-value", value)
    assert data[:1] == MAGIC_BYTE
    assert struct.unpack(">I", data[1:5])[0] == 42


def test_roundtrip_preserves_fields(codec: AvroCodec) -> None:
    now = datetime.now(tz=timezone.utc).replace(microsecond=0)
    value = {
        "envelope": {
            "event_id": "22222222-2222-2222-2222-222222222222",
            "event_version": 1,
            "occurred_at": now,
            "ingested_at": now,
            "source": "tle_producer",
            "trace_id": "trace-xyz",
        },
        "norad_id": "20580",
        "name": "HST",
        "position": {"lat_deg": 40.5, "lon_deg": -73.9, "alt_km": 540.0},
        "speed_km_s": 7.52,
        "healpix_cell": 12345,
        "tle_epoch": now,
        "sampled_at": now,
        "tle_source": "celestrak",
    }
    data = codec.encode("anduin.satellite.position.v1-value", value)
    parsed = codec.decode("anduin.satellite.position.v1-value", data)
    assert parsed["norad_id"] == "20580"
    assert parsed["position"]["lat_deg"] == 40.5
    assert parsed["tle_source"] == "celestrak"
    assert parsed["envelope"]["trace_id"] == "trace-xyz"
