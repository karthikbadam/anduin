"""Shared request dependencies."""
from __future__ import annotations

from fastapi import HTTPException, Request

from .auth import ApiKey


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
