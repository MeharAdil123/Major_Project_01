#!/usr/bin/env python3
"""Option A sanity check: mean per-carrier amplitude SD in consecutive 2 s blocks, per receiver, for the given take folders.

    python3 scripts/phase5_motion_timeline.py <take folder> ... > results/phase5/live_library/diag2_motion_timeline.log
"""
import sys, numpy as np
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from pipeline import build_dataset as bd, preprocess as pp
for f in sys.argv[1:]:
    _, per_rx = bd.load_take(Path(f)); g = pp.build_grid(per_rx)
    a = g["amp"]  # (rx, packets, carriers)
    print(Path(f).name)
    fs = pp.FS_IN; step = int(2*fs)
    for r in range(a.shape[0]):
        x = a[r]; x = x.reshape(x.shape[0], -1) if x.ndim > 2 else x
        sd = [np.nanmean(np.nanstd(x[i:i+step], axis=0)) for i in range(0, x.shape[0]-step+1, step)]
        print(f"  RX{r+1} amp sd per 2 s:", " ".join(f"{v:.2f}" for v in sd))
