"""Anduin query API (REST).

Stage 1 endpoints:
  GET /health
  GET /metrics
  GET /satellites/active?limit=N
  GET /satellites/{norad_id}
  GET /satellites/{norad_id}/track?window=5m
"""
from __future__ import annotations

import json
import logging
import re
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import asyncpg
import redis.asyncio as redis_asyncio
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from .auth import ApiKey, KeyLookup
from .config import settings
from .deps import require_api_key
from .hot_cells import HotCellsConsumer
from .ratelimit import RateLimiter
from .routes_passes import router as passes_router
from .routes_zones import router as zones_router
from .ws import WsHub, router as ws_router

log = logging.getLogger("query-api")
logging.basicConfig(level=logging.INFO)

WINDOW_RE = re.compile(r"^(\d+)(s|m|h)$")


def _parse_window(s: str) -> timedelta:
    m = WINDOW_RE.match(s)
    if not m:
        raise HTTPException(status_code=400, detail="window must be like '5m', '30s', '2h'")
    n, unit = int(m.group(1)), m.group(2)
    return timedelta(seconds=n) if unit == "s" else (
        timedelta(minutes=n) if unit == "m" else timedelta(hours=n)
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pg_pool = await asyncpg.create_pool(settings.postgres_dsn, min_size=1, max_size=5)
    app.state.redis = redis_asyncio.from_url(settings.redis_url, decode_responses=True)
    app.state.auth = KeyLookup(app.state.pg_pool)
    app.state.limiter = RateLimiter(app.state.redis)

    app.state.ws_hub = WsHub(
        settings.kafka_bootstrap,
        settings.schema_registry_url,
        app.state.redis,
    )
    await app.state.ws_hub.start()

    app.state.hot_cells = HotCellsConsumer(settings.kafka_bootstrap, app.state.redis)
    await app.state.hot_cells.start()

    log.info("startup ok")
    try:
        yield
    finally:
        await app.state.hot_cells.stop()
        await app.state.ws_hub.stop()
        await app.state.pg_pool.close()
        await app.state.redis.aclose()


app = FastAPI(title="anduin-query-api", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list(),
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["X-API-Key", "X-Trace-Id", "Content-Type", "traceparent"],
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

# Mount WebSocket + REST routers.
app.include_router(ws_router)
app.include_router(passes_router)
app.include_router(zones_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": settings.service_name}


@app.get("/satellites/active")
async def list_active(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    _key: ApiKey = Depends(require_api_key),
) -> dict:
    """Active satellites ranked by last-seen (Redis ZSET `sats:active`,
    highest score = most recent).
    """
    redis: redis_asyncio.Redis = request.app.state.redis
    raw = await redis.zrevrange("sats:active", 0, limit - 1, withscores=True)
    ids = [(nid, int(score)) for nid, score in raw]

    # Attach latest track sample per id so the frontend can render with one call.
    pipe = redis.pipeline()
    for nid, _ in ids:
        pipe.lindex(f"sats:track:{nid}", 0)
    tracks = await pipe.execute()

    items = []
    for (nid, score_ms), track_json in zip(ids, tracks, strict=True):
        payload = json.loads(track_json) if track_json else None
        items.append(
            {
                "norad_id": nid,
                "last_seen_ms": score_ms,
                "last_seen": datetime.fromtimestamp(score_ms / 1000, tz=timezone.utc),
                "position": payload,
            }
        )
    return {"items": items, "count": len(items)}


@app.get("/satellites/{norad_id}")
async def get_satellite(
    norad_id: str, request: Request, _key: ApiKey = Depends(require_api_key)
) -> dict:
    row = await request.app.state.pg_pool.fetchrow(
        """
        SELECT norad_id, name, classification, last_tle_epoch, created_at, updated_at
          FROM satellites WHERE norad_id = $1
        """,
        norad_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="unknown norad_id")
    return dict(row)


@app.get("/satellites/{norad_id}/track")
async def get_track(
    norad_id: str,
    request: Request,
    window: str = Query("5m", description="e.g. 30s, 5m, 2h"),
    _key: ApiKey = Depends(require_api_key),
) -> dict:
    """Recent position samples. Reads from Redis list first (fast), falls
    back to Postgres if list is empty or window exceeds Redis retention."""
    delta = _parse_window(window)
    cutoff = datetime.now(tz=timezone.utc) - delta

    redis: redis_asyncio.Redis = request.app.state.redis
    raw = await redis.lrange(f"sats:track:{norad_id}", 0, -1)
    if raw:
        samples = []
        for s in raw:
            d = json.loads(s)
            ts = datetime.fromtimestamp(d["t"] / 1000, tz=timezone.utc)
            if ts < cutoff:
                break  # newest-first ordering; stop at boundary
            samples.append({"t": ts, "lat": d["lat"], "lon": d["lon"], "alt": d["alt"], "v": d["v"]})
        if samples:
            return {"norad_id": norad_id, "source": "redis", "samples": samples}

    # Cold fallback.
    rows = await request.app.state.pg_pool.fetch(
        """
        SELECT sampled_at, lat_deg, lon_deg, alt_km, speed_km_s
          FROM satellite_positions
         WHERE norad_id = $1 AND sampled_at >= $2
         ORDER BY sampled_at DESC
         LIMIT 1000
        """,
        norad_id, cutoff,
    )
    return {
        "norad_id": norad_id,
        "source": "postgres",
        "samples": [
            {"t": r["sampled_at"], "lat": r["lat_deg"], "lon": r["lon_deg"],
             "alt": r["alt_km"], "v": r["speed_km_s"]}
            for r in rows
        ],
    }
