#!/usr/bin/env python3
"""Validate the environment check on recorded takes (replayed through the engine, simulated clock).

    python3 scripts/phase5_envcheck.py > results/phase5/envcheck.log

Empty-room takes should pass. Takes with a person in the room should NOT pass (the check assumes an empty
room; a person present must be caught). Caveat: the 7 empty takes are also the baseline and the presence
model's training data, so their "pass" is optimistic (in-sample); the occupied takes are the real test.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import engine as E  # noqa: E402
from app.consistency import SimClock  # noqa: E402
from pipeline import preprocess as pp  # noqa: E402
from ml.predict import Predictor  # noqa: E402

EMPTY = sorted(p.parent.name for p in (ROOT / "data" / "raw").glob("*none*/meta.json"))
OCCUPIED = [sorted(p.parent.name for p in (ROOT / "data" / "raw").glob(f"*_{s}_T*_{a}*/meta.json"))[0]
            for a in ("sit", "stand", "lie", "walk") for s in ("S5", "S6")]


def loo_baseline(sid):
    """Baseline rebuilt without take `sid` (leave-one-take-out) from data/features + data/processed."""
    import json
    import numpy as np
    import pandas as pd
    from ml import evaluate as ev
    from ml.train_final import env_profile
    base = json.loads((ROOT / "models" / "env_baseline.json").read_text())
    df = pd.read_csv(ROOT / "data" / "features" / "features_4s.csv")
    cols = base["dynamic"]["names"]
    e = (df["window_label"] == "empty").to_numpy() & (df["session_id"] != sid).to_numpy()
    F = df.loc[e, cols].to_numpy(float)
    base["dynamic"].update(mean=F.mean(0).tolist(), std=(F.std(0) + 1e-12).tolist(),
                           p05=np.percentile(F, 5, 0).tolist(), p95=np.percentile(F, 95, 0).tolist())
    base["profiles_db"] = {k: v for k, v in base["profiles_db"].items() if k != sid}
    return base


def check(folder, pred, seconds, baseline=None):
    clock = SimClock()
    buf = E.Buffer(clock=clock)
    eng = E.Engine(pred, buf, log_dir=None, clock=clock)
    eng.start_env_check(seconds)
    if baseline is not None:
        eng.envcheck.baseline = baseline
    ev = E.take_packets(folder)
    s0 = ev[0][0]
    nxt = s0 + 100
    for seq, r, raw, rssi in ev:
        while seq >= nxt:
            clock.t = (nxt - s0) / pp.FS_IN
            eng.step()
            nxt += 100
        clock.t = (seq - s0) / pp.FS_IN
        buf.push(r, seq, raw, rssi)
    return eng.env


def main():
    pred = Predictor(ROOT / "models")
    for group, takes in (("EMPTY (should pass; baseline leave-one-take-out, presence model in-sample)", EMPTY),
                         ("OCCUPIED (should NOT pass)", OCCUPIED)):
        print(f"\n== {group}")
        for sid in takes:
            env = check(ROOT / "data" / "raw" / sid, pred, 24.0,      # 30 s takes: 24 s of windows
                        loo_baseline(sid) if "none" in sid else None)
            if env.get("state") != "done":
                print(f"{sid:<30} not finished: {env}")
                continue
            print(f"{sid:<30} {env['verdict']:<45} z {env['dyn_z']:.2f}  outside {env['dyn_outside']:.2f}  "
                  f"occupied {env['occupied']:.2f}  fall {env['fall']:.2f}  profile dB {env['profile_db_vs_nearest'][0]:.1f}/"
                  f"{env['profile_db_vs_nearest'][1]:.1f} (nearest {env['nearest_training_take'][9:]})  windows {env['windows']}"
                  + (f"\n{'':<32}reasons: {'; '.join(env['reasons'])}" if env["reasons"] else ""), flush=True)


if __name__ == "__main__":
    main()
