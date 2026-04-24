"""API-key auth. Shared logic with ingest-api; extract to package after Stage 3."""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

import asyncpg


@dataclass
class ApiKey:
    key_id: str
    owner: str
    scopes: list[str]
    rate_per_minute: int


class KeyLookup:
    def __init__(self, pool: asyncpg.Pool, cache_ttl_s: int = 60):
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
