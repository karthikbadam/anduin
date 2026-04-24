"""Per-API-key Redis token bucket via Lua.

Uses a single EVAL: read (tokens, last_ms), refill based on elapsed, then
deduct 1 token if available. Atomic, single-round-trip. Shared verbatim with
query-api until a third consumer appears — then extract to a package.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Awaitable, Callable

import redis.asyncio as redis_asyncio
from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

# Token bucket: capacity = rate_per_minute, refill rate = rate/60 per second.
# KEYS[1] = bucket key. ARGV: capacity, now_ms.
# Returns: {allowed (0|1), retry_after_ms}.
LUA_TOKEN_BUCKET = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local now_ms = tonumber(ARGV[2])
local refill_ms_per_token = 60000 / capacity

local state = redis.call('HMGET', key, 'tokens', 'last_ms')
local tokens = tonumber(state[1])
local last_ms = tonumber(state[2])
if tokens == nil then
  tokens = capacity
  last_ms = now_ms
end

local elapsed = math.max(0, now_ms - last_ms)
local refilled = math.min(capacity, tokens + elapsed / refill_ms_per_token)

if refilled >= 1 then
  local new_tokens = refilled - 1
  redis.call('HMSET', key, 'tokens', new_tokens, 'last_ms', now_ms)
  redis.call('EXPIRE', key, 120)
  return {1, 0}
else
  redis.call('HMSET', key, 'tokens', refilled, 'last_ms', now_ms)
  redis.call('EXPIRE', key, 120)
  local need = 1 - refilled
  local retry_ms = math.ceil(need * refill_ms_per_token)
  return {0, retry_ms}
end
"""

BYPASS_PATHS = {"/health", "/metrics", "/docs", "/openapi.json", "/redoc"}


@dataclass
class RateLimitResult:
    allowed: bool
    retry_after_ms: int


class RateLimiter:
    def __init__(self, client: redis_asyncio.Redis):
        self.client = client
        self._sha: str | None = None

    async def _script_sha(self) -> str:
        if self._sha is None:
            self._sha = await self.client.script_load(LUA_TOKEN_BUCKET)
        return self._sha

    async def check(self, key_id: str, capacity: int) -> RateLimitResult:
        sha = await self._script_sha()
        now_ms = int(time.time() * 1000)
        try:
            res = await self.client.evalsha(
                sha, 1, f"ratelimit:{key_id}", capacity, now_ms
            )
        except redis_asyncio.ResponseError:
            # Script cache may have been flushed; reload and retry once.
            self._sha = None
            sha = await self._script_sha()
            res = await self.client.evalsha(
                sha, 1, f"ratelimit:{key_id}", capacity, now_ms
            )
        allowed, retry_after_ms = int(res[0]), int(res[1])
        return RateLimitResult(bool(allowed), retry_after_ms)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limiter: RateLimiter):
        super().__init__(app)
        self.limiter = limiter

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path in BYPASS_PATHS:
            return await call_next(request)
        key = getattr(request.state, "api_key", None)
        if key is None:
            # Auth middleware should have populated this; if not, fail safe.
            return await call_next(request)
        result = await self.limiter.check(key.key_id, key.rate_per_minute)
        if not result.allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="rate limit exceeded",
                headers={"Retry-After": str(max(1, result.retry_after_ms // 1000))},
            )
        return await call_next(request)
