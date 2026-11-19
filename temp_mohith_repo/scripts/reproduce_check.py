#!/usr/bin/env python3
"""Compare a reproduction run with the committed state (used by scripts/reproduce.sh).

    python3 scripts/reproduce_check.py <scratch features dir> <scratch models dir>

1. features_4s.csv rebuilt from data/raw vs data/features/features_4s.csv: same rows and ids, max |difference|
   per numeric column.
2. models retrained into the scratch dir vs models/: predicted labels and probabilities of every task on all
   4 s windows of data/features/features_4s.csv.
"""
import sys
from pathlib import Path

import joblib
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml import features as fx  # noqa: E402


def main(feat_dir: Path, models_dir: Path) -> int:
    ok = True
    a = pd.read_csv(ROOT / "data" / "features" / "features_4s.csv")
    b = pd.read_csv(feat_dir / "features_4s.csv")
    print(f"1. features_4s.csv: committed {a.shape}, rebuilt {b.shape}")
    if a.shape != b.shape or list(a.columns) != list(b.columns) or not (a["session_id"].values == b["session_id"].values).all():
        print("   DIFFERENT rows/columns/ids")
        ok = False
    else:
        num = a.select_dtypes("number").columns
        d = (a[num] - b[num]).abs().max()
        nonnum = [c for c in a.columns if c not in num and not (a[c].astype(str) == b[c].astype(str)).all()]
        print(f"   numeric columns {len(num)}: max |diff| {d.max():.3g} (column {d.idxmax()}); "
              f"non-numeric columns differing: {nonnum or 'none'}")
        ok &= d.max() < 1e-6 and not nonnum
    names = fx.feature_names()
    print("2. retrained models vs models/ (all 4 s windows):")
    for task in ("presence", "state", "events", "fall_alarm"):
        pa, pb = ROOT / "models" / task, models_dir / task
        if not (pa / "model.joblib").exists():
            continue
        cols = [names.index(c) for c in json.loads((pa / "model_meta.json").read_text())["feature_names"]]
        X = a[[names[c] for c in cols]].to_numpy(np.float64)
        ma, mb = joblib.load(pa / "model.joblib"), joblib.load(pb / "model.joblib")
        la, lb = ma.predict(X), mb.predict(X)
        dp = np.abs(ma.predict_proba(X) - mb.predict_proba(X)).max()
        agree = float(np.mean(la == lb))
        print(f"   {task:10s} labels agree {agree * 100:.2f} % of {len(X)}; max |prob diff| {dp:.3g}")
        ok &= agree == 1.0
    print("RESULT:", "reproduced" if ok else "differences found (see above)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
