#!/usr/bin/env python3
"""Format 1 (data/raw/<session>/) -> Format 2 (data/processed/windows_*.npz). See docs/CONTRACTS.md.

    python3 -m pipeline.build_dataset                       # data/raw -> data/processed
    python3 -m pipeline.build_dataset --raw data_synth/raw --out data_synth/processed

State takes  -> 2 s windows every 1 s (first and last second of a take skipped).
Event takes  -> windows centred on the movement peak found after the cue
                (5 windows, shifted -0.3..+0.3 s, all from the same take).
Windows failing the quality gate (missing > 10 % or gap > 100 ms on any receiver) are dropped
and counted in index.csv.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from host import csiwire as cw  # noqa: E402
from pipeline import preprocess as pp  # noqa: E402

STATE_HOP_S = 1.0
EDGE_SKIP_S = 1.0
EVENT_SEARCH_S = (0.0, 4.0)          # look for the movement peak in [cue, cue+4 s]
EVENT_SHIFTS_S = (-0.3, -0.15, 0.0, 0.15, 0.3)


def motion_energy(grid) -> np.ndarray:
    """Per-packet movement measure: mean |d/dt| of gain-normalised amplitude, both RX, 0.2 s smoothed."""
    a = pp.normalise(grid["amp"])                          # [R, L, S]
    d = np.abs(np.diff(a, axis=1)).mean(axis=(0, 2))
    d = np.concatenate([[d[0]], d])
    k = int(0.2 * pp.FS_IN)
    return np.convolve(d, np.ones(k) / k, mode="same")


def load_take(folder: Path):
    meta = json.loads((folder / "meta.json").read_text())
    per_rx = {}
    for r in pp.RX_IDS:
        f = folder / f"RX{r}.bin"
        if f.exists():
            per_rx[r] = pp.records_from_recording(cw.load(f))
    return meta, per_rx


def take_windows(meta, grid):
    L = grid["amp"].shape[1]
    span = pp.WIN * pp.DECIM
    if meta["kind"] == "state":
        hop = int(STATE_HOP_S * pp.FS_IN)
        skip = int(EDGE_SKIP_S * pp.FS_IN)
        starts = list(range(skip, L - span - skip + 1, hop))
        return pp.cut_windows(grid, starts), None
    # event
    e = motion_energy(grid)
    cue = int((meta.get("cue_s") or 0) * pp.FS_IN)
    lo = min(L - 1, cue + int(EVENT_SEARCH_S[0] * pp.FS_IN))
    hi = min(L, cue + int(EVENT_SEARCH_S[1] * pp.FS_IN))
    peak = lo + int(np.argmax(e[lo:hi])) if hi > lo else L // 2
    starts = [peak - span // 2 + int(s * pp.FS_IN) for s in EVENT_SHIFTS_S]
    return pp.cut_windows(grid, starts), peak / pp.FS_IN


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", type=Path, default=ROOT / "data" / "raw")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "processed")
    ap.add_argument("--include-invalid", action="store_true")
    a = ap.parse_args()

    takes = sorted(p.parent for p in a.raw.glob("*/meta.json") if not p.parent.name.startswith("_"))
    if not takes:
        print(f"no takes in {a.raw}")
        return 1
    bank = {"state": [], "event": []}
    index = []
    synthetic = False
    for folder in takes:
        meta, per_rx = load_take(folder)
        synthetic |= bool(meta.get("synthetic"))
        row = dict(session_id=meta["session_id"], kind=meta["kind"], activity=meta["activity"],
                   subject=meta["subject"], position=meta["position"], valid=meta.get("valid", True),
                   receivers=",".join(f"RX{r}" for r in per_rx), windows=0, rejected=0, peak_s="", note="")
        if not meta.get("valid", True) and not a.include_invalid:
            row["note"] = "skipped: marked invalid"
            index.append(row)
            continue
        if len(per_rx) < len(pp.RX_IDS):
            row["note"] = "skipped: missing receiver"
            index.append(row)
            continue
        try:
            grid = pp.build_grid(per_rx)
        except ValueError as e:
            row["note"] = f"skipped: {e}"
            index.append(row)
            continue
        w, peak = take_windows(meta, grid)
        ok = w["ok"]
        row.update(windows=int(ok.sum()), rejected=int((~ok).sum()),
                   peak_s=round(peak, 2) if peak is not None else "")
        if ok.any():
            n = int(ok.sum())
            bank[meta["kind"]].append(dict(
                X=w["X"][ok].astype(np.float16), rssi=w["rssi"][ok].astype(np.float16),
                miss_frac=w["miss_frac"][ok].astype(np.float32),
                t_start=(w["start_pkt"][ok] / pp.FS_IN).astype(np.float32),
                y=np.array([meta["activity"]] * n), session_id=np.array([meta["session_id"]] * n),
                subject=np.array([meta["subject"]] * n), position=np.array([meta["position"]] * n)))
        index.append(row)
        print(f"{meta['session_id']:<45} {meta['kind']:<5} {meta['activity']:<9} windows {row['windows']:>3} "
              f"rejected {row['rejected']}" + (f"  peak {row['peak_s']} s" if peak is not None else ""))

    a.out.mkdir(parents=True, exist_ok=True)
    for kind, parts in bank.items():
        if not parts:
            continue
        cat = {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}
        classes = np.array(sorted(set(cat["y"].tolist())))
        np.savez_compressed(a.out / f"windows_{kind}.npz", **cat, classes=classes,
                            preproc_version=pp.PREPROC_VERSION, fs=pp.FS, used_sc=pp.USED_SC,
                            synthetic=synthetic)
        counts = {c: int((cat["y"] == c).sum()) for c in classes}
        print(f"\nwindows_{kind}.npz: X {cat['X'].shape}, classes {counts}")
    with open(a.out / "index.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(index[0]))
        wr.writeheader()
        wr.writerows(index)
    if synthetic:
        print("\nWARNING: dataset contains SYNTHETIC takes - results say nothing about real performance")
    print(f"written to {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
