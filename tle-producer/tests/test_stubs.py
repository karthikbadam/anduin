"""Guard-rails on the TODO(me) stubs and their drift fallbacks."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.healpix import lonlat_to_healpix, stub_cell
from app.propagate import parse_tle_epoch, propagate_position, stub_propagate


def test_propagate_position_is_unimplemented() -> None:
    with pytest.raises(NotImplementedError):
        propagate_position("1 25544U 98067A ...", "2 25544 ...", datetime.now(tz=timezone.utc))


def test_lonlat_to_healpix_is_unimplemented() -> None:
    with pytest.raises(NotImplementedError):
        lonlat_to_healpix(0.0, 0.0)


def test_stub_propagate_returns_moving_positions() -> None:
    t0 = datetime(2026, 4, 23, tzinfo=timezone.utc)
    p0 = stub_propagate("25544", t0)
    p1 = stub_propagate("25544", t0 + timedelta(minutes=10))
    assert -90 <= p0.lat_deg <= 90
    assert -180 <= p0.lon_deg < 180
    assert p0.alt_km >= 0
    assert (p0.lat_deg, p0.lon_deg) != (p1.lat_deg, p1.lon_deg)


def test_stub_cell_in_valid_range() -> None:
    nside = 64
    assert 0 <= stub_cell(0.0, 0.0, nside) < 12 * nside * nside
    assert 0 <= stub_cell(-179.9, 89.9, nside) < 12 * nside * nside


def test_parse_tle_epoch() -> None:
    # Day 100.5 of 2026 → 2026-04-10 12:00 UTC (day 100 = Apr 10, .5 = noon)
    line1 = "1 25544U 98067A   26100.50000000  .00012345  00000-0  23456-3 0  9995"
    dt = parse_tle_epoch(line1)
    assert dt.year == 2026
    assert dt.month == 4
    assert dt.day == 10
