import sys
from pathlib import Path
import numpy as np
import pandas as pd

mohith_repo = Path("temp_mohith_repo").resolve()
sys.path.insert(0, str(mohith_repo))

from ml import deep as dp
from ml import evaluate as ev

npz_path = mohith_repo / "data" / "processed" / "windows_4s.npz"
csv_path = mohith_repo / "data" / "features" / "features_4s.csv"
out_path = Path("data/channels_4s.npy")
out_path.parent.mkdir(exist_ok=True, parents=True)

if out_path.exists():
    print(f"{out_path} already exists! Size: {out_path.stat().st_size / 1e6:.1f} MB", flush=True)
else:
    print(f"Reading {npz_path}...", flush=True)
    df = pd.read_csv(csv_path, usecols=ev.META_COLS)
    z = np.load(npz_path, allow_pickle=False)
    print(f"Converting {len(df)} windows to 32 channels...", flush=True)
    C = np.concatenate([dp.channels(z["X"][i:i + 256], z["P"][i:i + 256]) for i in range(0, len(df), 256)])
    print(f"Saving to {out_path}...", flush=True)
    np.save(out_path, C)
    print(f"Done! Saved shape: {C.shape}, size: {out_path.stat().st_size / 1e6:.1f} MB", flush=True)
