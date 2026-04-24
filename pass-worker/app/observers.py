"""Active-observer set. Kept in Redis ZSET `observers:active` so query-api can
add/remove observers without a direct handle to pass-worker.

Members are hashes `observer_id` (sha256(lat|lon)[:16]); the value per member is
a JSON blob {lat, lon, alt} stored at `observer:{observer_id}`.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import redis.asyncio as redis_asyncio

ACTIVE_ZSET = "observers:active"
DETAIL_PREFIX = "observer:"


def observer_id(lat: float, lon: float) -> str:
    digest = hashlib.sha256(f"{lat:.6f}|{lon:.6f}".encode()).hexdigest()
    return digest[:16]


@dataclass
class Observer:
    observer_id: str
    lat_deg: float
    lon_deg: float
    alt_km: float = 0.0


async def load_all(r: redis_asyncio.Redis) -> list[Observer]:
    ids = await r.zrange(ACTIVE_ZSET, 0, -1)
    if not ids:
        return []
    pipe = r.pipeline()
    for oid in ids:
        pipe.get(f"{DETAIL_PREFIX}{oid}")
    blobs = await pipe.execute()
    out: list[Observer] = []
    for oid, blob in zip(ids, blobs, strict=True):
        if not blob:
            continue
        try:
            j = json.loads(blob)
        except json.JSONDecodeError:
            continue
        out.append(Observer(oid, j.get("lat"), j.get("lon"), j.get("alt", 0.0)))
    return out
