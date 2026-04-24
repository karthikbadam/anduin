from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field


class TleSource(str, Enum):
    fixture = "fixture"
    replay = "replay"
    celestrak = "celestrak"
    n2yo = "n2yo"
    spacetrack = "spacetrack"
    unknown = "unknown"


Lat = Annotated[float, Field(ge=-90, le=90)]
Lon = Annotated[float, Field(ge=-180, lt=180)]
AltKm = Annotated[float, Field(ge=0, le=100_000)]


class SatellitePositionIn(BaseModel):
    norad_id: str = Field(min_length=1, max_length=10)
    name: str | None = None
    lat_deg: Lat
    lon_deg: Lon
    alt_km: AltKm
    speed_km_s: float = Field(ge=0, le=30)
    healpix_cell: int = Field(ge=0)
    tle_epoch: datetime
    sampled_at: datetime
    tle_source: TleSource = TleSource.unknown


class TleIn(BaseModel):
    norad_id: str = Field(min_length=1, max_length=10)
    name: str | None = None
    line1: str = Field(min_length=1, max_length=80)
    line2: str = Field(min_length=1, max_length=80)
    classification: str | None = None
    tle_epoch: datetime
    source: TleSource = TleSource.unknown


class AckResponse(BaseModel):
    event_id: str
    topic: str
