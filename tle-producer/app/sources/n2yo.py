"""N2YO adapter — stubbed. Requires N2YO_API_KEY; 1000 req/hr free tier."""
from __future__ import annotations

from ..config import settings


class N2yoSource:
    async def fetch(self) -> list[dict]:
        if not settings.n2yo_api_key:
            raise RuntimeError("N2YO_API_KEY not set — dev should use TLE_SOURCE=fixture")
        raise NotImplementedError("n2yo adapter stubbed for production use")
