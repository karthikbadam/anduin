"""Observer + pass endpoints.

- POST /observers {lat, lon, alt?} registers a lat/lon with pass-worker via Redis.
- GET  /observers lists currently registered observers.
- GET  /passes?lat&lon&hours=24 returns upcoming passes for that lat/lon.
  Passes are read from Redis list `passes:{observer_id}` (pass-worker populates
  it as a side-effect of publishing events; Stage 2 scaffolding does this via a
  Kafka consumer tailing satellite.pass.v1 — Stage 3 hardens durability).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from .auth import ApiKey
from .deps import require_api_key

router = APIRouter()

OBS_ACTIVE = "observers:active"
OBS_DETAIL_PREFIX = "observer:"
PASSES_PREFIX = "passes:"


def _observer_id(lat: float, lon: float) -> str:
    return hashlib.sha256(f"{lat:.6f}|{lon:.6f}".encode()).hexdigest()[:16]


class ObserverIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, lt=180)
    alt_km: float = Field(default=0.0, ge=0, le=10)


class ObserverOut(BaseModel):
    observer_id: str
    lat: float
    lon: float
    alt_km: float


@router.post("/observers", response_model=ObserverOut)
async def register_observer(
    payload: ObserverIn,
    request: Request,
    _key: ApiKey = Depends(require_api_key),
) -> ObserverOut:
    oid = _observer_id(payload.lat, payload.lon)
    r = request.app.state.redis
    detail = json.dumps({"lat": payload.lat, "lon": payload.lon, "alt": payload.alt_km})
    now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    pipe = r.pipeline()
    pipe.set(f"{OBS_DETAIL_PREFIX}{oid}", detail, ex=3 * 3600)  # 3h idle eviction
    pipe.zadd(OBS_ACTIVE, {oid: now_ms})
    await pipe.execute()
    return ObserverOut(observer_id=oid, lat=payload.lat, lon=payload.lon, alt_km=payload.alt_km)


@router.get("/observers")
async def list_observers(
    request: Request,
    _key: ApiKey = Depends(require_api_key),
) -> dict:
    r = request.app.state.redis
    ids = await r.zrange(OBS_ACTIVE, 0, -1, withscores=True)
    if not ids:
        return {"items": [], "count": 0}
    out = []
    for oid, score in ids:
        raw = await r.get(f"{OBS_DETAIL_PREFIX}{oid}")
        if not raw:
            continue
        j = json.loads(raw)
        out.append({
            "observer_id": oid,
            "lat": j["lat"],
            "lon": j["lon"],
            "alt_km": j.get("alt", 0.0),
            "last_seen_ms": int(score),
        })
    return {"items": out, "count": len(out)}


@router.get("/passes")
async def list_passes(
    request: Request,
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, lt=180),
    hours: int = Query(24, ge=1, le=72),
    _key: ApiKey = Depends(require_api_key),
) -> dict:
    """Return upcoming pass events for the (lat, lon) location.
    Registers the observer on first call so pass-worker starts computing for it.
    """
    oid = _observer_id(lat, lon)
    r = request.app.state.redis
    # Keep observer alive.
    now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    await r.zadd(OBS_ACTIVE, {oid: now_ms})
    detail = await r.get(f"{OBS_DETAIL_PREFIX}{oid}")
    if not detail:
        await r.set(
            f"{OBS_DETAIL_PREFIX}{oid}",
            json.dumps({"lat": lat, "lon": lon, "alt": 0.0}),
            ex=3 * 3600,
        )

    cutoff = datetime.now(tz=timezone.utc) + timedelta(hours=hours)
    raw = await r.lrange(f"{PASSES_PREFIX}{oid}", 0, 500)
    items = []
    for s in raw:
        try:
            d = json.loads(s)
        except json.JSONDecodeError:
            continue
        # Only return events in the future window.
        t = datetime.fromisoformat(d.get("event_time")) if d.get("event_time") else None
        if t is None or t > cutoff:
            continue
        items.append(d)
    items.sort(key=lambda x: x.get("event_time", ""))
    return {"observer_id": oid, "items": items, "count": len(items), "window_hours": hours}
