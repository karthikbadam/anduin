"""SGP4 TLE propagation.

The real algorithm is `propagate_position` — a TODO(me) stub to implement.
A fallback `stub_propagate` returns drifting fixed positions so the Stage 1
pipeline (Kafka → persister → query-api → frontend map) can be demoed end to
end before SGP4 is filled in. Set env STUB_PROPAGATE=false to use the real one.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class PropagatedPosition:
    lat_deg: float        # [-90, 90]
    lon_deg: float        # [-180, 180)
    alt_km: float         # >= 0
    speed_km_s: float     # >= 0


# ───────────────────────── USER-OWNED STUB ─────────────────────────
def propagate_position(line1: str, line2: str, t_utc: datetime) -> PropagatedPosition:
    """TODO(me): propagate TLE to geodetic position at a given UTC time.

    I/O contract:
      Input:
        line1, line2 : str        # two TLE lines (~69 chars each)
        t_utc        : datetime   # tz-aware UTC timestamp
      Output:
        PropagatedPosition(lat_deg, lon_deg, alt_km, speed_km_s)
          lat_deg ∈ [-90, 90]
          lon_deg ∈ [-180, 180)
          alt_km  >= 0
          speed_km_s >= 0

    Equations to translate:
      1. SGP4 mean-motion + Kepler: use sgp4.api.Satrec.twoline2rv(line1, line2),
         then sat.sgp4(jd, fr) → (err, r_teme, v_teme) in km and km/s.
      2. TEME → ECEF via GMST rotation: R_z(-GMST) applied to r_teme.
      3. ECEF → geodetic (WGS84): lat/lon/alt via closed-form (Bowring) or
         iterative. WGS84 a=6378.137 km, f=1/298.257223563.

    Hints:
      - Skyfield's EarthSatellite wrapper does steps 1–3 in one call if you
        prefer; using it is fine — read the source so you understand why.
      - speed_km_s = ||v_teme|| is a fine approximation for LEO.
    """
    raise NotImplementedError("TODO(me): SGP4 → TEME → ECEF → geodetic")
# ────────────────────────────────────────────────────────────────────


def stub_propagate(norad_id: str, t_utc: datetime) -> PropagatedPosition:
    """Deterministic drift so the map shows motion before SGP4 is filled in.
    Different NORAD ids get different phases so sats don't overlap."""
    seed = sum(ord(c) for c in norad_id)
    # Elapsed seconds since an epoch we invent.
    t = t_utc.timestamp()
    # 90-minute period (typical LEO), varied slightly per sat.
    period_s = 90 * 60 + (seed % 30)
    phase = (t / period_s) * 2 * math.pi + seed * 0.3
    lat = 51.6 * math.sin(phase)            # ≈ ISS inclination
    lon = ((t / 60) * 2 + seed * 37) % 360  # drift 2°/min + per-sat offset
    if lon >= 180:
        lon -= 360
    alt = 400 + (seed % 7) * 30             # 400–600 km
    return PropagatedPosition(lat, lon, alt, 7.66)


def propagate(line1: str, line2: str, norad_id: str, t_utc: datetime, stub: bool) -> PropagatedPosition:
    """Dispatch: real SGP4 if stub=False, otherwise the drift helper."""
    if stub:
        return stub_propagate(norad_id, t_utc)
    return propagate_position(line1, line2, t_utc)


def parse_tle_epoch(line1: str) -> datetime:
    """Extract the epoch timestamp from TLE line 1 columns 19–32."""
    yy = int(line1[18:20])
    day = float(line1[20:32])
    year = 2000 + yy if yy < 57 else 1900 + yy
    # Jan 1 00:00 UTC + (day - 1) days
    from datetime import timedelta
    return datetime(year, 1, 1, tzinfo=timezone.utc) + timedelta(days=day - 1)
