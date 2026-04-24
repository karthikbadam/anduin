"""Pass-event detection from a stream of elevation samples."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

# Threshold list in the order we detect crossings within a single pass.
THRESHOLDS_DEG = [0.0, 10.0]

PassEventKind = Literal["rise_0", "rise_10", "culmination", "set_10", "set_0"]


@dataclass
class Sample:
    elev_deg: float
    t_utc: datetime


@dataclass
class PassState:
    last_peak_elev: float = -90.0
    peak_ts: datetime | None = None
    # Track what we've already emitted this pass so we don't double-fire.
    emitted: set[str] = field(default_factory=set)
    prev_prev: Sample | None = None  # for culmination inflection detection


@dataclass
class PassEvent:
    kind: PassEventKind
    t_utc: datetime
    elev_at_event: float


def _interpolate_crossing(prev: Sample, curr: Sample, threshold: float) -> datetime:
    """Linear interpolation of the UTC time at which elev == threshold."""
    dy = curr.elev_deg - prev.elev_deg
    if abs(dy) < 1e-9:
        return curr.t_utc
    frac = (threshold - prev.elev_deg) / dy
    dt = (curr.t_utc - prev.t_utc).total_seconds()
    return prev.t_utc + (curr.t_utc - prev.t_utc) * frac if dt > 0 else curr.t_utc


# ───────────────────────── USER-OWNED STUB ─────────────────────────
def detect_pass_event(
    prev: Sample | None, curr: Sample, state: PassState
) -> PassEvent | None:
    """TODO(me): detect pass events from elevation samples.

    Per SATFLOW §E.4, a pass emits 5 events:
      at 0° rising, 10° rising, culmination (local max), 10° setting, 0° setting.
    This function is called once per (sat, obs) per new sample and returns
    AT MOST one event to emit (None if no threshold crossing this sample).

    I/O contract:
      Input:
        prev  Sample(elev_deg, t_utc) | None   # previous sample, None if first
        curr  Sample(elev_deg, t_utc)          # new sample
        state PassState                        # mutate in place to track peak/emitted
      Output:
        PassEvent | None — kind ∈ {"rise_0","rise_10","culmination","set_10","set_0"}
                          with the interpolated UTC time of the crossing.

    Equation(s) to translate:
      - Zero-crossing of (elev − threshold): sign flips between prev and curr.
      - Linear-interpolated crossing time:
          t_cross = t_prev + (t_curr − t_prev) * (threshold − elev_prev) / (elev_curr − elev_prev)
      - Culmination: elev started decreasing after increasing. Use state.prev_prev:
          prev_prev.elev < prev.elev AND curr.elev < prev.elev ⇒ peak at prev.

    Hints:
      - `prev.elev < thr <= curr.elev` is a rise crossing; flip for set.
      - Culmination time should be prev.t_utc (the sample that turned out to be the peak),
        not interpolated. Don't emit more than one culmination per pass.
      - Reset `state.emitted` after "set_0" fires so the next pass can emit again.
    """
    raise NotImplementedError("TODO(me): threshold crossings + culmination peak")
# ────────────────────────────────────────────────────────────────────


def stub_detect_pass_event(
    prev: Sample | None, curr: Sample, state: PassState
) -> PassEvent | None:
    """Simple threshold + inflection detector — good enough for a demo."""
    if prev is None:
        state.prev_prev = None
        return None

    # Rising and setting threshold crossings.
    for thr in THRESHOLDS_DEG:
        key_rise = f"rise_{int(thr)}"
        key_set = f"set_{int(thr)}"
        if prev.elev_deg < thr <= curr.elev_deg and key_rise not in state.emitted:
            state.emitted.add(key_rise)
            t = _interpolate_crossing(prev, curr, thr)
            return PassEvent(kind=key_rise, t_utc=t, elev_at_event=thr)  # type: ignore[arg-type]
        if prev.elev_deg > thr >= curr.elev_deg and key_set not in state.emitted:
            state.emitted.add(key_set)
            t = _interpolate_crossing(prev, curr, thr)
            evt = PassEvent(kind=key_set, t_utc=t, elev_at_event=thr)  # type: ignore[arg-type]
            if key_set == "set_0":
                # End of pass — reset so next pass can emit fresh.
                state.emitted.clear()
                state.last_peak_elev = -90.0
                state.peak_ts = None
                state.prev_prev = None
            return evt

    # Culmination: previous was the peak (prev_prev < prev AND curr < prev).
    pp = state.prev_prev
    if (
        pp is not None
        and pp.elev_deg < prev.elev_deg
        and curr.elev_deg < prev.elev_deg
        and "culmination" not in state.emitted
        and prev.elev_deg > THRESHOLDS_DEG[-1]  # only if we actually went above 10°
    ):
        state.emitted.add("culmination")
        state.last_peak_elev = prev.elev_deg
        state.peak_ts = prev.t_utc
        state.prev_prev = prev
        return PassEvent(kind="culmination", t_utc=prev.t_utc,
                         elev_at_event=prev.elev_deg)

    state.prev_prev = prev
    return None


def detect(prev: Sample | None, curr: Sample, state: PassState, stub: bool) -> PassEvent | None:
    if stub:
        return stub_detect_pass_event(prev, curr, state)
    return detect_pass_event(prev, curr, state)
