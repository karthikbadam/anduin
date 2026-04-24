"""Replay adapter — Stage 2/3. Reads timestamped TLE snapshots and advances
through them as wall-clock time advances. Stubbed for Stage 1."""
from __future__ import annotations


class ReplaySource:
    async def fetch(self) -> list[dict]:
        raise NotImplementedError("replay adapter is Stage 2+")
