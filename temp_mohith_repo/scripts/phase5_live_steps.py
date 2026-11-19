#!/usr/bin/env python3
"""Final live test (2026-10-23 11:40): per-step results over the exact action intervals.

    python3 scripts/phase5_live_steps.py results/phase5/live_library/live_20261023_114052.jsonl \
        > results/phase5/live_library/live_steps_final.log

Intervals (wall clock) start at the spoken "go" cue (times from the session transcript; TEST_CONDITIONS.md).
State steps: windows ENDING from go + 4 s (the 4 s window lies fully inside the action) to go + 30 s.
Event steps (sit_down, stand_up, fall): windows ending from go to go + 10 s (an event window may straddle).
Per step: raw label and smoothed label counts, presence P(occupied) median, event argmax counts (not none), max P(fall),
fall alarms. The step's window is the prediction at that time; LOSO remains the evaluation.
"""
import collections
import json
import sys
from datetime import datetime

import numpy as np

STEPS = [  # name, go (wall), kind, duration s, expected (state or event)
    ("empty (final 30 s)", "11:52:28", "state", 30, "empty"),
    ("stand at A", "11:47:39", "state", 30, "stand"),
    ("walk path1 (vertical)", "11:48:42", "state", 30, "walk"),
    ("walk path2 (horizontal)", "11:49:44", "state", 30, "walk"),   # "go" issued 11:49:42-44; speech call returned late
    ("sit_down at A", "11:50:58", "event", 10, "sit_down"),
    ("stand_up at A", "11:51:14", "event", 10, "stand_up"),
    ("fall on mattress M", "11:51:55", "event", 10, "fall"),
]


def secs(w):
    t = datetime.strptime(w, "%H:%M:%S")
    return t.hour * 3600 + t.minute * 60 + t.second


def main(path):
    r = [json.loads(l) for l in open(path) if l.strip()]
    steps = [x for x in r if "status" in x]
    # engine time -> wall clock via the first step
    w0, t0 = secs(steps[0]["wall"]), steps[0]["t"]
    for x in steps:
        x["tw"] = w0 + (x["t"] - t0)
    print(f"log {path}; {len(steps)} steps")
    print("step | windows ok/total | raw label | smoothed label | P(occupied) median | events (argmax != none) | max P(fall) | alarms | correct (raw)")
    for name, go, kind, dur, exp in STEPS:
        g = secs(go)
        a, b = (g + 4, g + dur) if kind == "state" else (g, g + dur)
        seg = [x for x in steps if a <= x["tw"] <= b]
        ok = [x for x in seg if x["status"] == "ok"]
        raw = collections.Counter(x["label"] for x in ok)
        sm = collections.Counter(x["label_smoothed"] for x in ok)
        pocc = np.median([x["presence_prob"] for x in ok]) if ok else float("nan")
        ev = collections.Counter(x["event"] for x in ok if x.get("event") not in (None, "none"))
        fall = max((x.get("fall_prob") or 0) for x in ok) if ok else float("nan")
        al = [x["wall"] for x in seg if x.get("alert") == "FALL"]
        if kind == "state":
            corr = f"{raw.get(exp, 0)}/{len(ok)}"
        else:
            corr = f"event '{exp}' predicted in {ev.get(exp, 0)} windows" + (f"; alarm {al}" if exp == "fall" else "")
        print(f"{name} | {len(ok)}/{len(seg)} | {dict(raw.most_common())} | {dict(sm.most_common())} | {pocc:.2f} | "
              f"{dict(ev.most_common())} | {fall:.2f} | {al} | {corr}")
    al_all = [(x["wall"], round(x.get("fall_prob") or 0, 2)) for x in steps if x.get("alert") == "FALL"]
    print(f"\nall fall alarms in the session: {al_all}")


if __name__ == "__main__":
    main(sys.argv[1])
