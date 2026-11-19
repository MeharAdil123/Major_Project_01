#!/usr/bin/env python3
"""Analyse a live test log (Phase 5, library session): per marked segment, what the system reported.

    python3 scripts/phase5_live_analysis.py results/phase5/live_library/live_20261023_101819.jsonl \
        > results/phase5/live_library/analysis.log

A segment runs from one marker to the next. For each: steps by status (ok / degraded / no_signal / starting),
the smoothed label and event predictions on ok steps, the maximum fall probability, fall alarms, and receiver
health. This is a FUNCTIONAL test under the recorded conditions (TEST_CONDITIONS.md); the evaluation is LOSO.
"""
import collections
import json
import sys

import numpy as np


def main(path):
    r = [json.loads(l) for l in open(path) if l.strip()]
    steps = [x for x in r if "status" in x]
    marks = [x["marker"] for x in r if "marker" in x]
    print(f"log {path}: {len(steps)} steps, t 0 … {steps[-1]['t']:.1f} s ({steps[0]['wall']} … {steps[-1]['wall']}), "
          f"{len(marks)} markers")
    t = np.array([x["t"] for x in steps])
    print(f"step interval median {np.median(np.diff(t)):.2f} s, p90 {np.percentile(np.diff(t), 90):.2f} s")
    # environment checks from the per-step progress fields
    prev = None
    for x in steps:
        st = x.get("env_state")
        if st != prev:
            print(f"  env check state -> {st} at t {x['t']:.1f} ({x['wall']}), windows {x.get('env_windows')}")
            prev = st
    for x in r:
        if "env" in x:
            e = x["env"]
            print(f"  env result logged at t {x['t']:.1f}: {e['verdict']} {e['reasons']}")
    bounds = [(m["t"], m["label"], m["wall"]) for m in marks] + [(steps[-1]["t"] + 0.01, "end", steps[-1]["wall"])]
    bounds = [(0.0, "before first marker (incl. empty-room check)", steps[0]["wall"])] + bounds
    print("\nsegment | wall | dur s | steps ok/degr/no_sig/start | smoothed label (ok steps) | events (p>=0.6) | "
          "max P(fall) | alarms | RX1 / RX2 median rate, loss %")
    rows = []
    for (a, lab, wall), (b, _, _) in zip(bounds[:-1], bounds[1:]):
        seg = [x for x in steps if a <= x["t"] < b]
        if not seg:
            continue
        stc = collections.Counter(x["status"] for x in seg)
        ok = [x for x in seg if x["status"] == "ok"]
        labs = collections.Counter(x["label_smoothed"] for x in ok)
        evs = collections.Counter(x["event"] for x in ok if x.get("event") not in (None, "none"))
        fmax = max((x.get("fall_prob") or 0 for x in ok), default=0.0)
        al = [x["t"] for x in seg if x.get("alert")]
        rx = lambda k, f: np.median([x["rx"][k][f] or 0 for x in seg])  # noqa: E731
        lab_txt = ", ".join(f"{k} {v}" for k, v in labs.most_common(4)) or "—"
        ev_txt = ", ".join(f"{k} {v}" for k, v in evs.most_common(3)) or "—"
        print(f"{lab:<44} | {wall} | {b - a:5.1f} | {stc['ok']}/{stc['degraded']}/{stc['no_signal']}/{stc['starting']} | "
              f"{lab_txt} | {ev_txt} | {fmax:.2f} | {len(al)}{' at ' + ', '.join(f'{x:.1f}' for x in al) if al else ''} | "
              f"{rx('RX1', 'rate'):.0f}/{rx('RX2', 'rate'):.0f} pkt/s, {rx('RX1', 'loss_pct'):.1f}/{rx('RX2', 'loss_pct'):.1f} %")
        rows.append(dict(segment=lab, wall=wall, t0=a, t1=b, status=dict(stc), labels=dict(labs), events=dict(evs),
                         max_fall_prob=fmax, alarms=al))
    # RX2 unplug / replug timeline
    m_un = next((m for m in marks if m["label"] == "RX2 unplugged"), None)
    if m_un:
        print("\nRX2 reconnect timeline (from the unplug marker):")
        prev = None
        for x in steps:
            if x["t"] < m_un["t"] - 1:
                continue
            key = (x["status"], (x.get("reason") or "")[:40], x["rx"]["RX2"]["rate"] > 0)
            if key != prev:
                print(f"  t {x['t']:7.1f} ({x['wall']}) {x['status']:<9} RX2 rate {x['rx']['RX2']['rate']:>3}/s "
                      f"age {x['rx']['RX2']['age_s']}  {x.get('reason') or ''}")
                prev = key
            if x["t"] > m_un["t"] + 90:
                break
    json.dump(rows, open(path.replace(".jsonl", "_segments.json"), "w"), indent=1, default=float)


if __name__ == "__main__":
    main(sys.argv[1])
