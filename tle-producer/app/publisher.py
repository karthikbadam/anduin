"""HTTP publisher to ingest-api. Connection-pool bounded per SATFLOW plan."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import httpx

from .config import settings

log = logging.getLogger(__name__)

# Cap in-flight POSTs so a 1.8k-sat tick doesn't stampede the connection pool.
_INFLIGHT_CAP = 150


class IngestClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.ingest_api_url,
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=100, max_connections=200),
            headers={
                "X-API-Key": settings.anduin_dev_api_key,
                "Content-Type": "application/json",
            },
        )
        self._sem = asyncio.Semaphore(_INFLIGHT_CAP)

    async def post_position(
        self,
        *,
        norad_id: str,
        name: str | None,
        lat_deg: float,
        lon_deg: float,
        alt_km: float,
        speed_km_s: float,
        healpix_cell: int,
        tle_epoch: datetime,
        sampled_at: datetime,
        tle_source: str,
        trace_id: str | None = None,
    ) -> None:
        headers = {"traceparent": trace_id} if trace_id else {}
        body = {
            "norad_id": norad_id,
            "name": name,
            "lat_deg": lat_deg,
            "lon_deg": lon_deg,
            "alt_km": alt_km,
            "speed_km_s": speed_km_s,
            "healpix_cell": healpix_cell,
            "tle_epoch": tle_epoch.isoformat(),
            "sampled_at": sampled_at.isoformat(),
            "tle_source": tle_source,
        }
        async with self._sem:
            try:
                r = await self._client.post(
                    "/events/satellite-position", json=body, headers=headers
                )
                if r.status_code >= 400 and r.status_code != 429:
                    log.warning("ingest %d for %s: %s", r.status_code, norad_id, r.text)
            except httpx.HTTPError as e:
                log.warning("ingest error for %s: %s", norad_id, e)

    async def aclose(self) -> None:
        await self._client.aclose()
