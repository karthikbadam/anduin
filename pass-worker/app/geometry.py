"""Observer ↔ satellite look-angle geometry.

The real algorithm is `look_angles` — a TODO(me) stub. The fallback
`stub_look_angles` uses a rough great-circle-distance approximation so the
pipeline can demo before the user fills in ECEF/ENU math.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class ObserverGeo:
    lat_deg: float
    lon_deg: float
    alt_km: float = 0.0


@dataclass
class SatelliteGeo:
    lat_deg: float
    lon_deg: float
    alt_km: float


@dataclass
class LookAngles:
    elevation_deg: float   # [-90, 90]
    azimuth_deg: float     # [0, 360)
    range_km: float        # >= 0


# ───────────────────────── USER-OWNED STUB ─────────────────────────
def look_angles(obs: ObserverGeo, sat: SatelliteGeo) -> LookAngles:
    """TODO(me): compute look angles from observer to satellite.

    I/O contract:
      Input:  obs ObserverGeo(lat_deg, lon_deg, alt_km)
              sat SatelliteGeo(lat_deg, lon_deg, alt_km)
      Output: LookAngles(
                elevation_deg ∈ [-90, 90],   # angle above local horizon
                azimuth_deg   ∈ [0, 360),    # from local north, clockwise
                range_km      >= 0,          # slant distance
              )

    Equation(s) to translate:
      1. (lat, lon, alt) → ECEF (WGS84):
           N(φ) = a / sqrt(1 - e² sin²φ)
           x = (N + h) cosφ cosλ
           y = (N + h) cosφ sinλ
           z = (N (1 - e²) + h) sinφ
           WGS84: a = 6378.137 km, f = 1/298.257223563, e² = 2f - f²
      2. Δ = r_sat - r_obs
      3. Rotate Δ into observer-local ENU frame:
           [ E ]   [ -sinλ            cosλ            0    ] [Δx]
           [ N ] = [ -sinφ cosλ      -sinφ sinλ       cosφ ] [Δy]
           [ U ]   [  cosφ cosλ       cosφ sinλ       sinφ ] [Δz]
      4. range = ||Δ||,  elev = asin(U / range),  az = atan2(E, N) mod 2π

    Hints:
      - Work in radians throughout, convert to degrees only at the return.
      - Normalize azimuth to [0, 360) with (math.degrees(az) + 360) % 360.
    """
    raise NotImplementedError("TODO(me): geodetic → ECEF → ENU → elev/az/range")
# ────────────────────────────────────────────────────────────────────


def stub_look_angles(obs: ObserverGeo, sat: SatelliteGeo) -> LookAngles:
    """Rough spherical approximation for drift mode. Close enough for the
    frontend to show a plausible pass table before the real math is in place."""
    R = 6371.0
    phi_o = math.radians(obs.lat_deg)
    phi_s = math.radians(sat.lat_deg)
    lam_o = math.radians(obs.lon_deg)
    lam_s = math.radians(sat.lon_deg)
    d_lam = lam_s - lam_o

    # Central angle between observer and sub-satellite point.
    cos_sigma = (math.sin(phi_o) * math.sin(phi_s)
                 + math.cos(phi_o) * math.cos(phi_s) * math.cos(d_lam))
    cos_sigma = max(-1.0, min(1.0, cos_sigma))
    sigma = math.acos(cos_sigma)

    # Slant range via law of cosines on the (R_obs, R+alt, range) triangle.
    r_o = R + obs.alt_km
    r_s = R + sat.alt_km
    range_km = math.sqrt(r_o * r_o + r_s * r_s - 2 * r_o * r_s * math.cos(sigma))

    # Elevation from spherical approximation.
    if range_km < 1e-6:
        elev = 90.0
    else:
        cos_elev = (r_s * math.sin(sigma)) / range_km
        elev = math.degrees(math.asin(max(-1.0, min(1.0, 1 - (sigma * r_s) * 0 + 0))))  # placeholder
        # Better approximation: use elevation from local horizon plane:
        sin_e = (r_s * math.cos(sigma) - r_o) / range_km
        elev = math.degrees(math.asin(max(-1.0, min(1.0, sin_e))))

    # Azimuth from bearing formula.
    y = math.sin(d_lam) * math.cos(phi_s)
    x = math.cos(phi_o) * math.sin(phi_s) - math.sin(phi_o) * math.cos(phi_s) * math.cos(d_lam)
    az = (math.degrees(math.atan2(y, x)) + 360.0) % 360.0

    return LookAngles(elevation_deg=elev, azimuth_deg=az, range_km=range_km)


def compute(obs: ObserverGeo, sat: SatelliteGeo, stub: bool) -> LookAngles:
    if stub:
        return stub_look_angles(obs, sat)
    return look_angles(obs, sat)
