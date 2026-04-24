"""Token-bucket rate limiter — same Lua script as ingest-api."""
from __future__ import annotations

import time
from dataclasses import dataclass

import redis.asyncio as redis_asyncio

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
            self._sha = None
            sha = await self._script_sha()
            res = await self.client.evalsha(
                sha, 1, f"ratelimit:{key_id}", capacity, now_ms
            )
        return RateLimitResult(bool(int(res[0])), int(res[1]))
