"""Window labels for Format 2 v2 (Phase 3, D-040). Pure functions; no I/O.

State takes : every window gets the take's activity ("empty" for the empty room); source "state".
Event takes : the action interval [onset, end] comes from pipeline/onset.py (o2).
  event      overlap(window, interval) >= MIN_OVERLAP x min(interval length, window length)
  event_pre  window ends at least GUARD_S before the onset    -> pre-action posture
  event_post window starts at least GUARD_S after the end      -> end posture
  dropped    anything in between ("transition"), never labelled
  Takes whose interval is not usable for training (no detection, detection < 0.6 s, onset clipped
  because motion ran into the cue, or listed in EXCLUDE_EVENT) give NO event windows: only windows
  that end before the cue (minus a guard) are kept, as event_pre. The take still counts in the
  per-take evaluation, which does not depend on these labels.
Pre-action posture: stand (sit_down, fall, bend_pick), sit (stand_up); walk for falls whose
instruction starts with walking (D-038). End posture: sit, stand, lie (fall onto the mattress), stand.
"""
from __future__ import annotations

import numpy as np

MIN_OVERLAP = 0.5
GUARD_S = 0.3
PRE_STATE = {"sit_down": "stand", "fall": "stand", "bend_pick": "stand", "stand_up": "sit"}
POST_STATE = {"sit_down": "sit", "fall": "lie", "bend_pick": "stand", "stand_up": "stand"}
EXCLUDE_EVENT = {"20261022_S2_E57_fall", "20261022_S5_E39_fall", "20261022_S6_E39_fall"}   # D-038
EVENTS = ("fall", "sit_down", "stand_up", "bend_pick")
STATES = ("sit", "stand", "walk", "lie")


def starts_walking(meta: dict) -> bool:
    return "walk" in (meta.get("instruction") or "").lower().split("on the beep")[0]


def event_usable(meta: dict, onset: dict | None) -> tuple[bool, str]:
    """Can this event take's detected interval be used for event-window training?"""
    if meta["session_id"] in EXCLUDE_EVENT:
        return False, "excluded (D-038: motion runs into the cue)"
    if not onset or not onset.get("detected"):
        return False, "no action detected"
    if onset.get("early"):
        return False, "onset clipped (motion before the cue)"
    if onset.get("short"):
        return False, "detection shorter than 0.6 s"
    return True, ""


def label_windows(meta: dict, starts_s: np.ndarray, win_s: float, onset: dict | None = None):
    """starts_s: window start times in take time (s). Returns (labels, sources); label "" = dropped."""
    starts_s = np.asarray(starts_s, float)
    n = len(starts_s)
    if meta["kind"] == "state":
        return np.array([meta["activity"]] * n, dtype=object), np.array(["state"] * n, dtype=object)
    act = meta["activity"]
    pre = "walk" if starts_walking(meta) else PRE_STATE[act]
    post = POST_STATE[act]
    ends = starts_s + win_s
    labels = np.array([""] * n, dtype=object)
    src = np.array(["transition"] * n, dtype=object)
    usable, _ = event_usable(meta, onset)
    if usable:
        on, end = float(onset["onset"]), float(onset["end"])
        ov = np.clip(np.minimum(ends, end) - np.maximum(starts_s, on), 0, None)
        need = MIN_OVERLAP * min(end - on, win_s)
        ev = ov >= need
        labels[ev], src[ev] = act, "event"
        p = ~ev & (ends <= on - GUARD_S)
        labels[p], src[p] = pre, "event_pre"
        q = ~ev & (starts_s >= end + GUARD_S)
        labels[q], src[q] = post, "event_post"
    else:
        cue = float(meta.get("cue_s") or 0)
        p = ends <= cue - GUARD_S
        labels[p], src[p] = pre, "event_pre"
        if onset and onset.get("detected") and meta["session_id"] in EXCLUDE_EVENT:
            q = starts_s >= float(onset["end"]) + GUARD_S             # after the fall: lying (state use)
            labels[q], src[q] = post, "event_post"
    return labels, src
