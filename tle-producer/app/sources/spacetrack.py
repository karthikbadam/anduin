"""Space-Track adapter — stubbed. Requires account + credentials; TOS is strict."""
from __future__ import annotations

from ..config import settings


class SpacetrackSource:
    async def fetch(self) -> list[dict]:
        if not (settings.spacetrack_user and settings.spacetrack_password):
            raise RuntimeError("spacetrack creds not set — dev should use TLE_SOURCE=fixture")
        raise NotImplementedError("spacetrack adapter stubbed for production use")
