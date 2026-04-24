"""HEALPix encoding of geodetic points.

The real function is `lonlat_to_healpix` — a TODO(me) stub. A `stub_cell`
fallback returns a deterministic integer in the valid id range so the
pipeline types still match before the real one is implemented.
"""
from __future__ import annotations


# ───────────────────────── USER-OWNED STUB ─────────────────────────
def lonlat_to_healpix(lon_deg: float, lat_deg: float, nside: int = 64) -> int:
    """TODO(me): encode a (lon, lat) point as a HEALPix pixel id.

    I/O contract:
      Input:  lon_deg ∈ [-180, 180), lat_deg ∈ [-90, 90], nside (int, default 64)
      Output: int — HEALPix pixel id, NESTED ordering, 0 <= id < 12 * nside**2

    Equation to translate:
      θ (colatitude) = (90° − lat) · π/180   ∈ [0, π]
      φ (longitude)  = lon · π/180           ∈ [0, 2π)
      pixel_id       = ang2pix_nest(nside, θ, φ)

    Hints:
      - HEALPix uses COLATITUDE (from north pole) — this is the #1 bug to avoid.
      - Prefer astropy_healpix.HEALPix(nside, order='nested').lonlat_to_healpix
        with astropy.units; fall back to healpy.ang2pix if you want a lighter dep.
    """
    raise NotImplementedError("TODO(me): colatitude θ then ang2pix_nest")
# ────────────────────────────────────────────────────────────────────


def stub_cell(lon_deg: float, lat_deg: float, nside: int = 64) -> int:
    """Deterministic bucketing so the pipeline has a valid `healpix_cell` int
    before the real encoding is implemented. NOT HEALPix-correct — just a
    bucket from a (lon-bin, lat-bin) product that fits in the valid id range."""
    total = 12 * nside * nside
    lon_bin = int((lon_deg + 180) // 1) % 360   # 360 longitude bins
    lat_bin = int((lat_deg + 90) // 1) % 180    # 180 latitude bins
    return (lat_bin * 360 + lon_bin) % total


def encode_cell(lon_deg: float, lat_deg: float, nside: int, stub: bool) -> int:
    if stub:
        return stub_cell(lon_deg, lat_deg, nside)
    return lonlat_to_healpix(lon_deg, lat_deg, nside)
