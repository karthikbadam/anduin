"""TLE producer orchestrator.

Loop:
  - Every PROPAGATION_TICK_SECONDS: for each watchlist sat, propagate and POST.
  - Every BULK_CADENCE_SECONDS: emit one round-robin slice of the non-watchlist
    sats so the bulk dataset streams gradually (Stage 2 scale; Stage 1 only has
    the watchlist).
  - Every TLE_FETCH_INTERVAL_MINUTES: re-fetch TLEs from the configured source.
"""
from __future__ import annotations

import asyncio
import logging
import signal
from contextlib import suppress
from datetime import datetime, timezone

from .config import settings
from .healpix import encode_cell
from .propagate import propagate
from .publisher import IngestClient
from .sources import make_source

log = logging.getLogger("tle-producer")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


async def run() -> None:
    log.info("tle-producer start: source=%s stub_propagate=%s", settings.tle_source, settings.stub_propagate)
    source = make_source(settings.tle_source)
    client = IngestClient()
    tles = await source.fetch()
    watchlist = set(settings.watchlist())

    by_id = {t["norad_id"]: t for t in tles}
    log.info("loaded %d TLEs; watchlist %s", len(tles), sorted(watchlist))

    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with suppress(NotImplementedError):
            asyncio.get_event_loop().add_signal_handler(sig, stop.set)

    # Bulk cursor for round-robin slicing.
    bulk_ids = [nid for nid in by_id if nid not in watchlist]
    bulk_cursor = 0

    # Per-tick slice so the whole bulk catalog cycles once per BULK_CADENCE_SECONDS
    # without bursting. ceil() so trailing sats aren't left behind.
    def _bulk_slice_per_tick() -> int:
        if not bulk_ids:
            return 0
        ratio = settings.propagation_tick_seconds / settings.bulk_cadence_seconds
        return max(1, -(-len(bulk_ids) * int(ratio * 1000) // 1000))  # math.ceil w/o import

    last_refresh = _now()

    async def emit(nid: str) -> None:
        rec = by_id.get(nid)
        if not rec:
            return
        t = _now()
        pos = propagate(rec["line1"], rec["line2"], nid, t, stub=settings.stub_propagate)
        cell = encode_cell(pos.lon_deg, pos.lat_deg, settings.healpix_nside, stub=settings.stub_propagate)
        await client.post_position(
            norad_id=nid,
            name=rec.get("name"),
            lat_deg=pos.lat_deg,
            lon_deg=pos.lon_deg,
            alt_km=pos.alt_km,
            speed_km_s=pos.speed_km_s,
            healpix_cell=cell,
            tle_epoch=rec.get("epoch") or t,
            sampled_at=t,
            tle_source=rec.get("source", settings.tle_source),
        )

    try:
        while not stop.is_set():
            # Refresh TLEs on cadence.
            if (_now() - last_refresh).total_seconds() / 60 >= settings.tle_fetch_interval_minutes:
                try:
                    new_tles = await source.fetch()
                    by_id = {t["norad_id"]: t for t in new_tles}
                    bulk_ids = [nid for nid in by_id if nid not in watchlist]
                    log.info("TLE refresh: %d records", len(by_id))
                except Exception as e:  # noqa: BLE001
                    log.warning("TLE refresh failed: %s", e)
                last_refresh = _now()

            # Watchlist + bulk slice every tick — smooth load per plan §K.10.
            slice_size = _bulk_slice_per_tick()
            slice_ids = [
                bulk_ids[(bulk_cursor + i) % len(bulk_ids)]
                for i in range(slice_size)
            ] if bulk_ids else []
            if bulk_ids:
                bulk_cursor = (bulk_cursor + slice_size) % len(bulk_ids)

            tick_ids = list(watchlist & by_id.keys()) + slice_ids
            await asyncio.gather(*(emit(nid) for nid in tick_ids))

            try:
                await asyncio.wait_for(stop.wait(), timeout=settings.propagation_tick_seconds)
            except asyncio.TimeoutError:
                pass
    finally:
        await client.aclose()
        log.info("tle-producer stopped")


if __name__ == "__main__":
    asyncio.run(run())
