"""Celestrak live adapter.

Enforces a 180-min minimum fetch interval via an internal timestamp so repeated
process restarts can't hammer Celestrak. Uses the polite User-Agent from env.

CLI mode: `python -m app.sources.celestrak --refresh-fixture` fetches once and
writes `fixtures/active.txt`. Intended to be run by a human, rarely.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

import httpx

from ..config import settings
from .fixture import FIXTURES_DIR, _parse_tle_file

log = logging.getLogger(__name__)
URL_TMPL = "https://celestrak.org/NORAD/elements/gp.php?GROUP={group}&FORMAT=tle"
_STATE_PATH = FIXTURES_DIR / ".celestrak_last_fetch_ms"


def _last_fetch_ms() -> int:
    try:
        return int(_STATE_PATH.read_text().strip())
    except (FileNotFoundError, ValueError):
        return 0


def _write_last_fetch(ts_ms: int) -> None:
    try:
        _STATE_PATH.write_text(str(ts_ms))
    except OSError:
        pass  # best-effort


class CelestrakSource:
    async def fetch(self) -> list[dict]:
        elapsed_min = (time.time() * 1000 - _last_fetch_ms()) / 60000
        if elapsed_min < settings.tle_fetch_interval_minutes:
            remaining = settings.tle_fetch_interval_minutes - elapsed_min
            log.info(
                "celestrak fetch throttled: %.1f min until next allowed; "
                "using previous active.txt", remaining,
            )
            active = FIXTURES_DIR / "active.txt"
            if active.exists():
                return _parse_tle_file(active.read_text())
            raise RuntimeError("no cached active.txt and fetch is throttled")

        # Try configured group; on 403 fall back to `stations` (small, always allowed).
        groups_to_try = [settings.celestrak_group]
        if settings.celestrak_group != "stations":
            groups_to_try.append("stations")

        async with httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": settings.celestrak_user_agent},
        ) as client:
            last_err: Exception | None = None
            for group in groups_to_try:
                url = URL_TMPL.format(group=group)
                log.info("celestrak fetch → %s", url)
                r = await client.get(url)
                if r.status_code == 200 and r.text.strip():
                    log.info("celestrak: group=%s ok (%d bytes)", group, len(r.text))
                    break
                last_err = RuntimeError(
                    f"celestrak group={group} returned {r.status_code}"
                )
                log.warning("%s — trying next group", last_err)
            else:
                raise last_err or RuntimeError("no celestrak group succeeded")
        (FIXTURES_DIR / "active.txt").write_text(r.text)
        _write_last_fetch(int(time.time() * 1000))
        return _parse_tle_file(r.text)


def _cli() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-fixture", action="store_true",
                        help="Fetch Celestrak active.txt once and exit.")
    args = parser.parse_args()
    if args.refresh_fixture:
        async def _run():
            # Force-refresh ignores the 180-min gate since the user is running this by hand.
            _write_last_fetch(0)
            src = CelestrakSource()
            tles = await src.fetch()
            print(f"wrote {len(tles)} TLEs to {FIXTURES_DIR/'active.txt'}")
        asyncio.run(_run())
        return
    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _cli()
