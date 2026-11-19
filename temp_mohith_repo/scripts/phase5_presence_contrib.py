#!/usr/bin/env python3
"""Why does the presence model say "occupied" on an empty take? Logistic-regression contributions per feature.

    python3 scripts/phase5_presence_contrib.py <take folder> ... > results/phase5/live_library/presence_contrib.log

Contribution of feature j = coef_j * (x_j - mean_j) / scale_j (the model's own scaler); the logit is their sum plus
the intercept. Per take: median over windows (0.5 s hop, 4 s windows, gate-ok only), the top features by |median
contribution|, and each feature's median value as a percentile of the 22 Oct empty-room windows.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import phase5_diag_analysis as da  # noqa: E402
from ml import features as fx  # noqa: E402
from ml.predict import Predictor  # noqa: E402


def main():
    pred = Predictor(ROOT / "models")
    pipe = pred.models["presence"]
    cols = pred.cols["presence"]
    names = [fx.feature_names()[c] for c in cols]
    sc, lr = pipe.named_steps["sc"], pipe.named_steps["m"]
    coef = lr.coef_[0]                                        # positive = toward "occupied"
    f22 = pd.read_csv(ROOT / "data" / "features" / "features_4s.csv")
    emp22 = f22[f22.activity_label == "empty"][names].to_numpy(float)
    print(f"presence model: {len(names)} features; classes {list(lr.classes_)}; intercept {lr.intercept_[0]:+.2f}")
    print(f"22 Oct empty windows for percentiles: {len(emp22)}")
    for arg in sys.argv[1:]:
        folder = Path(arg)
        meta = json.loads((folder / "meta.json").read_text())
        _, w, _, _ = da.windows(folder, meta)
        F = np.array([fx.window_features(w["X"][i], w["P"][i], w["rssi"][i])[cols]
                      for i in range(len(w["ok"])) if w["ok"][i]], float)
        C = coef * (F - sc.mean_) / sc.scale_
        logit = C.sum(1) + lr.intercept_[0]
        med = np.median(C, 0)
        print(f"\n-- {folder.name} ({meta['activity']}): windows {len(F)}, median logit {np.median(logit):+.2f} "
              f"(P(occ) {1 / (1 + np.exp(-np.median(logit))):.2f}); sum of median contributions {med.sum():+.2f}")
        for j in np.argsort(-np.abs(med))[:10]:
            v = np.median(F[:, j])
            pct = 100 * np.mean(emp22[:, j] < v)
            print(f"   {names[j]:28s} contrib {med[j]:+6.2f}  coef {coef[j]:+5.2f}  value {v:10.4g}  "
                  f"pct of 22 Oct empty {pct:5.1f}")


if __name__ == "__main__":
    main()
