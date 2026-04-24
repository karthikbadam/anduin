"""API-key authentication middleware.

Looks up `X-API-Key` against the `api_keys` Postgres table by sha256 hash.
Results are cached in-process for 60 seconds. `/health` and `/metrics` bypass.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Awaitable, Callable

import asyncpg
from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

BYPASS_PATHS = {"/health", "/metrics", "/docs", "/openapi.json", "/redoc"}


@dataclass
class ApiKey:
    key_id: str
    owner: str
    scopes: list[str]
    rate_per_minute: int


class ApiKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, pool: asyncpg.Pool, cache_ttl_s: int = 60):
        super().__init__(app)
        self.pool = pool
        self._cache: dict[bytes, tuple[ApiKey, float]] = {}
        self._ttl = cache_ttl_s

    async def lookup(self, raw_key: str) -> ApiKey | None:
        digest = hashlib.sha256(raw_key.encode("utf-8")).digest()
        now = time.monotonic()
        hit = self._cache.get(digest)
        if hit and now - hit[1] < self._ttl:
            return hit[0]

        row = await self.pool.fetchrow(
            """
            SELECT key_id::text, owner, scopes, rate_per_minute
              FROM api_keys
             WHERE key_hash = $1 AND disabled_at IS NULL
            """,
            digest,
        )
        if not row:
            return None
        key = ApiKey(
            key_id=row["key_id"],
            owner=row["owner"],
            scopes=list(row["scopes"]),
            rate_per_minute=row["rate_per_minute"],
        )
        self._cache[digest] = (key, now)
        return key

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path in BYPASS_PATHS:
            return await call_next(request)

        raw = request.headers.get("x-api-key")
        if not raw:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing x-api-key")
        key = await self.lookup(raw)
        if key is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid api key")

        request.state.api_key = key
        return await call_next(request)
