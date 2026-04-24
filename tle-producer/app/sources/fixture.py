"""Read TLEs from a file on disk. Prefers active.txt, falls back to seed.txt."""
from __future__ import annotations

import logging
from pathlib import Path

from ..propagate import parse_tle_epoch

FIXTURES_DIR = Path(__file__).parents[2] / "fixtures"
log = logging.getLogger(__name__)


def _parse_tle_file(text: str) -> list[dict]:
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    out: list[dict] = []
    i = 0
    while i + 2 < len(lines) + 1:
        # TLE format: 3 lines per sat (name, line1, line2).
        if i + 2 >= len(lines):
            break
        name = lines[i].strip()
        l1 = lines[i + 1]
        l2 = lines[i + 2]
        if not (l1.startswith("1 ") and l2.startswith("2 ")):
            i += 1  # misaligned; skip
            continue
        norad_id = l1[2:7].strip()
        try:
            epoch = parse_tle_epoch(l1)
        except Exception:  # noqa: BLE001
            epoch = None
        out.append({
            "norad_id": norad_id,
            "name": name,
            "line1": l1,
            "line2": l2,
            "epoch": epoch,
            "source": "fixture",
        })
        i += 3
    return out


class FixtureSource:
    async def fetch(self) -> list[dict]:
        active = FIXTURES_DIR / "active.txt"
        seed = FIXTURES_DIR / "seed.txt"
        chosen = active if active.exists() else seed
        if not chosen.exists():
            raise RuntimeError(f"no fixture file at {active} or {seed}")
        records = _parse_tle_file(chosen.read_text())
        log.info("loaded %d TLEs from %s", len(records), chosen.name)
        return records
