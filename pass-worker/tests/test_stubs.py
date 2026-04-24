"""Guard-rails on Stage 2 TODO(me) stubs + behavior of stub fallbacks."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.geometry import ObserverGeo, SatelliteGeo, look_angles, stub_look_angles
from app.passes import PassState, Sample, detect_pass_event, stub_detect_pass_event


def test_look_angles_unimplemented() -> None:
    with pytest.raises(NotImplementedError):
        look_angles(ObserverGeo(0, 0, 0), SatelliteGeo(0, 0, 400))


def test_detect_pass_event_unimplemented() -> None:
    with pytest.raises(NotImplementedError):
        detect_pass_event(None, Sample(0.0, datetime.now(tz=timezone.utc)), PassState())


def test_stub_look_angles_overhead_satellite_high_elev() -> None:
    # Sat directly over observer → elev close to 90°, range ≈ alt.
    obs = ObserverGeo(37.77, -122.42, 0)
    sat = SatelliteGeo(37.77, -122.42, 400)
    la = stub_look_angles(obs, sat)
    assert la.elevation_deg > 85.0
    assert abs(la.range_km - 400) < 5.0


def test_stub_look_angles_below_horizon() -> None:
    # Sat on opposite side of earth → negative elevation.
    obs = ObserverGeo(0, 0, 0)
    sat = SatelliteGeo(0, 180, 400)
    la = stub_look_angles(obs, sat)
    assert la.elevation_deg < 0
    assert 0 <= la.azimuth_deg < 360


def test_stub_detect_pass_event_rise_and_set_fire_once() -> None:
    t0 = datetime(2026, 4, 23, tzinfo=timezone.utc)
    state = PassState()
    # Ascending through 0° rising:
    assert stub_detect_pass_event(None, Sample(-5, t0), state) is None
    ev = stub_detect_pass_event(Sample(-5, t0), Sample(5, t0 + timedelta(seconds=5)), state)
    assert ev is not None and ev.kind == "rise_0"
    # Continue to 10° rising:
    ev2 = stub_detect_pass_event(Sample(5, t0 + timedelta(seconds=5)),
                                  Sample(20, t0 + timedelta(seconds=10)), state)
    assert ev2 is not None and ev2.kind == "rise_10"
    # Culmination (peak at sample n-1):
    ev3 = stub_detect_pass_event(Sample(20, t0 + timedelta(seconds=10)),
                                  Sample(30, t0 + timedelta(seconds=15)), state)
    # 30 > 20, not a culmination yet.
    assert ev3 is None
    ev4 = stub_detect_pass_event(Sample(30, t0 + timedelta(seconds=15)),
                                  Sample(25, t0 + timedelta(seconds=20)), state)
    assert ev4 is not None and ev4.kind == "culmination"
    # Descending through 10°:
    ev5 = stub_detect_pass_event(Sample(25, t0 + timedelta(seconds=20)),
                                  Sample(5, t0 + timedelta(seconds=25)), state)
    assert ev5 is not None and ev5.kind == "set_10"
    # Descending through 0°:
    ev6 = stub_detect_pass_event(Sample(5, t0 + timedelta(seconds=25)),
                                  Sample(-3, t0 + timedelta(seconds=30)), state)
    assert ev6 is not None and ev6.kind == "set_0"
    # State resets after set_0 so a next rise still fires.
    ev7 = stub_detect_pass_event(Sample(-3, t0 + timedelta(seconds=30)),
                                  Sample(2, t0 + timedelta(seconds=35)), state)
    assert ev7 is not None and ev7.kind == "rise_0"
