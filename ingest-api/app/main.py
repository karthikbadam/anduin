"""Anduin ingest API.

Validates inbound events, wraps them in anduin.common.Envelope, encodes with
Confluent wire format, and produces to Kafka. API-key auth + Redis token-bucket.
"""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import asyncpg
import redis.asyncio as redis_asyncio
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from .auth import ApiKey, ApiKeyMiddleware
from .avro_codec import AvroCodec
from .config import settings
from .producers import KafkaProducerWrapper
from .ratelimit import RateLimiter
from .schemas import AckResponse, SatellitePositionIn, TleIn

log = logging.getLogger("ingest-api")
logging.basicConfig(level=logging.INFO)

TOPIC_POSITION = "anduin.satellite.position.v1"
TOPIC_TLE = "anduin.satellite.tle.v1"
SUBJECT_POSITION = f"{TOPIC_POSITION}-value"
SUBJECT_TLE = f"{TOPIC_TLE}-value"


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _envelope(trace_id: str | None) -> dict:
    now = _now()
    return {
        "event_id": str(uuid.uuid4()),
        "event_version": 1,
        "occurred_at": now,
        "ingested_at": now,
        "source": "tle_producer",
        "trace_id": trace_id,
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pg_pool = await asyncpg.create_pool(
        settings.postgres_dsn, min_size=1, max_size=5
    )
    app.state.redis = redis_asyncio.from_url(settings.redis_url, decode_responses=False)

    codec = AvroCodec(settings.schema_registry_url)
    await codec.load([SUBJECT_POSITION, SUBJECT_TLE])
    app.state.codec = codec
    app.state.kafka = KafkaProducerWrapper(settings.kafka_bootstrap, codec)
    app.state.auth = ApiKeyMiddleware(None, app.state.pg_pool)
    app.state.limiter = RateLimiter(app.state.redis)

    log.info("startup ok: %s loaded", [SUBJECT_POSITION, SUBJECT_TLE])
    try:
        yield
    finally:
        app.state.kafka.flush(5.0)
        await app.state.pg_pool.close()
        await app.state.redis.aclose()


app = FastAPI(title="anduin-ingest-api", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list(),
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["X-API-Key", "X-Trace-Id", "Content-Type", "traceparent"],
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


async def require_api_key(request: Request) -> ApiKey:
    raw = request.headers.get("x-api-key")
    if not raw:
        raise HTTPException(status_code=401, detail="missing x-api-key")
    key = await request.app.state.auth.lookup(raw)
    if key is None:
        raise HTTPException(status_code=401, detail="invalid api key")
    request.state.api_key = key

    result = await request.app.state.limiter.check(key.key_id, key.rate_per_minute)
    if not result.allowed:
        raise HTTPException(
            status_code=429,
            detail="rate limit exceeded",
            headers={"Retry-After": str(max(1, result.retry_after_ms // 1000))},
        )
    return key


@app.middleware("http")
async def inject_trace(request: Request, call_next):
    trace = request.headers.get("traceparent") or request.headers.get("x-trace-id")
    request.state.trace_id = trace
    response = await call_next(request)
    if trace:
        response.headers["x-trace-id"] = trace
    return response


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": settings.service_name}


@app.post(
    "/events/satellite-position",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=AckResponse,
)
async def post_position(
    payload: SatellitePositionIn,
    request: Request,
    _key: ApiKey = Depends(require_api_key),
) -> AckResponse:
    env = _envelope(trace_id=request.state.trace_id)
    value = {
        "envelope": env,
        "norad_id": payload.norad_id,
        "name": payload.name,
        "position": {
            "lat_deg": payload.lat_deg,
            "lon_deg": payload.lon_deg,
            "alt_km": payload.alt_km,
        },
        "speed_km_s": payload.speed_km_s,
        "healpix_cell": payload.healpix_cell,
        "tle_epoch": payload.tle_epoch,
        "sampled_at": payload.sampled_at,
        "tle_source": payload.tle_source.value,
    }
    request.app.state.kafka.publish(TOPIC_POSITION, SUBJECT_POSITION, payload.norad_id, value)
    return AckResponse(event_id=env["event_id"], topic=TOPIC_POSITION)


@app.post("/events/tle", status_code=status.HTTP_202_ACCEPTED, response_model=AckResponse)
async def post_tle(
    payload: TleIn,
    request: Request,
    _key: ApiKey = Depends(require_api_key),
) -> AckResponse:
    env = _envelope(trace_id=request.state.trace_id)
    value = {
        "envelope": env,
        "norad_id": payload.norad_id,
        "name": payload.name,
        "line1": payload.line1,
        "line2": payload.line2,
        "classification": payload.classification,
        "tle_epoch": payload.tle_epoch,
        "fetched_at": _now(),
        "source": payload.source.value,
    }
    request.app.state.kafka.publish(TOPIC_TLE, SUBJECT_TLE, payload.norad_id, value)
    return AckResponse(event_id=env["event_id"], topic=TOPIC_TLE)
