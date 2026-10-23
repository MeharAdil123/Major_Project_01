"""Version-controlled configuration: position map (D-027), take overrides (D-018), empty-take folds."""
import csv

import numpy as np
import pytest

from pipeline import positions as pos

ROOT = pos.ROOT


def test_position_map_corrected_paths():
    m = pos.load()
    assert m["version"] == 2
    p1, p2 = m["positions"]["path1"], m["positions"]["path2"]
    assert p1["relation"] == "along_link" and p1["x"][0] == p1["x"][1] == -1.5
    assert p2["relation"] == "across_link" and p2["y"][0] == p2["y"][1] == 2.55
    assert pos.centre("A") == (-0.9, 3.2)
    assert pos.centre("M") == pytest.approx((0.5, 3.35))
    assert pos.centre("none") is None
    assert m["boards"]["RX2"] == {"x": 1.3, "y": 4.5, "h": 0.5}


def test_every_plan_position_is_mapped():
    names = set(pos.load()["positions"])
    for plan in ("plan_subject_lib.csv", "plan_short.csv", "plan_empty.csv", "plan_empty_short.csv", "plan_s3_fix.csv"):
        with open(ROOT / "protocol" / plan, newline="") as f:
            for row in csv.DictReader(f):
                assert row["position"] in names, (plan, row["position"])


def test_take_overrides_file():
    with open(ROOT / "config" / "take_overrides.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    assert list(rows[0]) == ["session_id", "use", "reason"]
    t29 = [r for r in rows if r["session_id"] == "20261022_S1_T29_walk"]
    assert len(t29) == 1 and t29[0]["use"] == "true" and t29[0]["reason"]


def test_empty_takes_dealt_to_folds_take_by_take():
    """Gate 0 item 9: empty-room takes are distinct sessions, each dealt whole to one fold, on different folds."""
    import pandas as pd
    from ml.evaluate import assign_folds
    sessions = ["20261022_none_B00_empty", "20261022_none_B01_empty", "20261022_none_B01_empty_r2",
                "20261022_none_B01_empty_r4"]
    df = pd.DataFrame(dict(subject=["none"] * 8 + ["S1", "S2", "S3", "S4"],
                           session_id=[s for s in sessions for _ in range(2)] + ["a", "b", "c", "d"]))
    g = assign_folds(df)
    sess = df["session_id"].to_numpy()
    per_take = {s: set(g[sess == s].tolist()) for s in sessions}
    assert all(len(v) == 1 for v in per_take.values())               # a take never splits
    assert len({next(iter(v)) for v in per_take.values()}) == 4        # 4 takes -> 4 different folds
