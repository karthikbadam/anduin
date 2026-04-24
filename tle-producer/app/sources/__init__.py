"""Source adapter selector. Defaults to `fixture` (offline)."""
from __future__ import annotations

from typing import Protocol


class TleSource(Protocol):
    async def fetch(self) -> list[dict]: ...
    """Return a list of {norad_id, name, line1, line2, epoch, source}."""


def make_source(kind: str):
    from .fixture import FixtureSource
    from .replay import ReplaySource
    from .celestrak import CelestrakSource
    from .n2yo import N2yoSource
    from .spacetrack import SpacetrackSource

    table = {
        "fixture": FixtureSource,
        "replay": ReplaySource,
        "celestrak": CelestrakSource,
        "n2yo": N2yoSource,
        "spacetrack": SpacetrackSource,
    }
    if kind not in table:
        raise ValueError(f"unknown TLE_SOURCE: {kind}")
    return table[kind]()
