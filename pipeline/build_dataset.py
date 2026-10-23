#!/usr/bin/env python3
"""Format 1 (data/raw/<session>/) -> Format 2 v2 windows + feature CSV. See docs/CONTRACTS.md.

    python3 -m pipeline.build_dataset --win 3                 # one window length per run (memory)
    python3 -m pipeline.build_dataset --win 2 --max-miss 0.20 --max-gap 20

Per take: config/take_overrides.csv is applied (meta.json is never edited); RX1/RX2 are aligned on
one grid (pipeline/preprocess.py v2); event takes get their action interval from pipeline/onset.py
(o2; takes that start walking use the global still baseline); windows are cut (state takes: hop 1 s,
first/last second skipped; event takes: hop 0.5 s over the whole take), labelled
(pipeline/labels.py), passed through the quality gate, and featurised (ml/features.py f2).

Outputs
  data/processed/windows_<len>s.npz        X, P float16 [N,2,T,114]; rssi [N,2,T]; labels and ids
  data/features/features_<len>s.csv        one row per kept, labelled window: ids, labels, rx miss, features
  data/processed/index_<len>s.csv          per take: windows kept / rejected by gate / dropped by labelling
  data/processed/windows_<len>s_index.csv  per window (also rejected/dropped ones) with the reason
  data/processed/onsets.csv                per event take: detected interval and whether usable
  data/processed/index.csv                 copy of index_3s.csv (the default length)
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from host import csiwire as cw  # noqa: E402
from ml import features as fx  # noqa: E402
from pipeline import labels as lb  # noqa: E402
from pipeline import onset as od  # noqa: E402
from pipeline import preprocess as pp  # noqa: E402

STATE_HOP_S = 1.0
EVENT_HOP_S = 0.5
EDGE_SKIP_S = 1.0
DATASET_VERSION = "d2"


def motion_energy(grid) -> np.ndarray:
    """LEGACY (v1, replaced by pipeline/onset.py o1/o2, D-034). Kept only so the Phase 2 comparison scripts
    (scripts/phase2_peaks.py, phase2_figures.py) can be re-run. Mean |d/dt| of gain-normalised amplitude
    between consecutive 200 Hz packets, both RX, 0.2 s smoothed. Not used by the v2 pipeline."""
    a = pp.normalise(grid["amp"])                          # [R, L, S]
    d = np.abs(np.diff(a, axis=1)).mean(axis=(0, 2))
    d = np.concatenate([[d[0]], d])
    k = int(0.2 * pp.FS_IN)
    return np.convolve(d, np.ones(k) / k, mode="same")


def load_overrides(path=ROOT / "config" / "take_overrides.csv") -> dict:
    if not Path(path).exists():
        return {}
    with open(path, newline="") as f:
        return {r["session_id"]: r for r in csv.DictReader(f)}


def load_take(folder: Path):
    meta = json.loads((folder / "meta.json").read_text())
    per_rx = {}
    for r in pp.RX_IDS:
        f = folder / f"RX{r}.bin"
        if f.exists():
            per_rx[r] = pp.records_from_recording(cw.load(f))
    return meta, per_rx


def take_valid(meta, overrides) -> tuple[bool, str]:
    o = overrides.get(meta["session_id"])
    if o is not None:
        return o["use"].strip().lower() == "true", f"override: {o['reason'][:60]}"
    return bool(meta.get("valid", True)), "" if meta.get("valid", True) else "marked invalid"


def window_starts(meta, L, win_s):
    span = int(round(win_s * pp.FS_IN))
    if meta["kind"] == "state":
        hop, skip = int(STATE_HOP_S * pp.FS_IN), int(EDGE_SKIP_S * pp.FS_IN)
        return list(range(skip, L - span - skip + 1, hop))
    return list(range(0, L - span + 1, int(EVENT_HOP_S * pp.FS_IN)))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", type=Path, default=ROOT / "data" / "raw")
    ap.add_argument("--processed", type=Path, default=ROOT / "data" / "processed")
    ap.add_argument("--features", type=Path, default=ROOT / "data" / "features")
    ap.add_argument("--win", type=float, default=pp.WIN_S, help="window length in s (2, 3 or 4)")
    ap.add_argument("--max-miss", type=float, default=pp.MAX_MISS_FRAC)
    ap.add_argument("--max-gap", type=int, default=pp.MAX_GAP_PKTS)
    ap.add_argument("--limit", type=int, default=0, help="only the first N takes (testing)")
    a = ap.parse_args()
    t0 = time.time()
    tag = f"{a.win:g}s"
    overrides = load_overrides()
    folders = sorted(p.parent for p in a.raw.glob("*/meta.json") if not p.parent.name.startswith("_"))
    if a.limit:
        folders = folders[:a.limit]
    metas = {f: json.loads((f / "meta.json").read_text()) for f in folders}
    # still-start event takes first, so the global still baseline exists for walking-start takes
    folders.sort(key=lambda f: (metas[f]["kind"] == "event" and lb.starts_walking(metas[f]), f.name))
    still_pre = []
    names = fx.feature_names()
    bank = {k: [] for k in ("X", "P", "rssi", "miss_frac", "max_gap", "t_start", "y", "source", "session_id",
                            "subject", "position", "take_id", "activity", "kind")}
    feats, take_rows, win_rows, onset_rows = [], [], [], []
    for f in folders:
        meta, per_rx = load_take(f)
        sid = meta["session_id"]
        ok_take, why = take_valid(meta, overrides)
        trow = dict(session_id=sid, subject=meta["subject"], kind=meta["kind"], activity=meta["activity"],
                    position=meta["position"], used=ok_take, note=why, candidates=0, kept=0,
                    rejected_gate=0, dropped_label=0, event_windows=0)
        if not ok_take or len(per_rx) < len(pp.RX_IDS):
            trow["note"] = why or "missing receiver"
            take_rows.append(trow)
            continue
        grid = pp.build_grid(per_rx)
        L = grid["amp"].shape[1]
        first = min(int(d["seq"][0]) for d in per_rx.values())
        off_s = (grid["seq0"] - first) / pp.FS_IN             # take time of grid index 0
        onset = None
        if meta["kind"] == "event":
            t, m = od.motion_signal(grid)
            cue_g = meta["cue_s"] - off_s
            walking = lb.starts_walking(meta)
            pre = (t >= od.PRE_FROM_S) & (t <= cue_g - od.PRE_GUARD_S)
            if not walking:
                still_pre.append(np.median(m[:, pre], axis=1))
            base = np.median(still_pre, axis=0) if walking else None
            d = od.detect(t, m, cue_g, baseline=base)
            onset = dict(detected=d["detected"], onset=d["onset"] + off_s, end=d["end"] + off_s,
                         early=d["early"], short=d["short"], peak_ratio=d["peak_ratio"])
            usable, uwhy = lb.event_usable(meta, onset)
            onset_rows.append(dict(session_id=sid, subject=meta["subject"], activity=meta["activity"],
                                   position=meta["position"], starts_walking=walking,
                                   detected=onset["detected"], onset_s=round(onset["onset"], 3),
                                   end_s=round(onset["end"], 3), peak_ratio=round(onset["peak_ratio"], 2),
                                   early=onset["early"], short=onset["short"], usable_for_event_training=usable,
                                   reason=uwhy, onset_version=od.ONSET_VERSION))
        starts = window_starts(meta, L, a.win)
        w = pp.cut_windows(grid, starts, a.win, a.max_miss, a.max_gap)
        st_s = w["start_pkt"] / pp.FS_IN + off_s
        labels, src = lb.label_windows(meta, st_s, a.win, onset)
        trow["candidates"] = len(starts)
        for i in range(len(w["ok"])):
            reason = "ok" if w["ok"][i] else "gate"
            if labels[i] == "":
                reason = "dropped (transition)" if reason == "ok" else "gate+transition"
            win_rows.append(dict(session_id=sid, t_start=round(float(st_s[i]), 3), label=labels[i], source=src[i],
                                 rx1_miss=round(float(w["miss_frac"][i, 0]), 4), rx2_miss=round(float(w["miss_frac"][i, 1]), 4),
                                 rx1_maxgap=int(w["max_gap"][i, 0]), rx2_maxgap=int(w["max_gap"][i, 1]), status=reason))
        keep = w["ok"] & (labels != "")
        trow["rejected_gate"] = int((~w["ok"]).sum())
        trow["dropped_label"] = int((w["ok"] & (labels == "")).sum())
        trow["kept"] = int(keep.sum())
        trow["event_windows"] = int((keep & (src == "event")).sum())
        take_rows.append(trow)
        if not keep.any():
            continue
        idx = np.flatnonzero(keep)
        F = fx.batch_features(w["X"][idx], w["P"][idx], w["rssi"][idx])
        n = len(idx)
        bank["X"].append(w["X"][idx].astype(np.float16))
        bank["P"].append(w["P"][idx].astype(np.float16))
        bank["rssi"].append(w["rssi"][idx].astype(np.float16))
        bank["miss_frac"].append(w["miss_frac"][idx].astype(np.float32))
        bank["max_gap"].append(w["max_gap"][idx].astype(np.int16))
        bank["t_start"].append(st_s[idx].astype(np.float32))
        for k, v in (("y", labels[idx]), ("source", src[idx])):
            bank[k].append(np.asarray(v, dtype=str))
        for k, v in (("session_id", sid), ("subject", meta["subject"]), ("position", meta["position"]),
                     ("take_id", meta["take_id"]), ("activity", meta["activity"]), ("kind", meta["kind"])):
            bank[k].append(np.array([v] * n))
        for j, i in enumerate(idx):
            feats.append([sid, meta["subject"], meta["take_id"], meta["activity"], labels[i], meta["position"],
                          round(float(st_s[i]), 3), round(float(w["miss_frac"][i, 0]), 4),
                          round(float(w["miss_frac"][i, 1]), 4), src[i], meta["kind"]] + F[j].tolist())
        print(f"{sid:<36} {meta['kind']:<5} {meta['activity']:<9} kept {trow['kept']:>3} gate-rejected "
              f"{trow['rejected_gate']:>2} dropped {trow['dropped_label']:>2} event {trow['event_windows']:>2}"
              + (f"  onset {onset['onset']:.2f}-{onset['end']:.2f}" if onset and onset["detected"] else
                 ("  no action detected" if onset else "")), flush=True)

    a.processed.mkdir(parents=True, exist_ok=True)
    a.features.mkdir(parents=True, exist_ok=True)
    cat = {k: np.concatenate(v) for k, v in bank.items()}
    np.savez(a.processed / f"windows_{tag}.npz", **cat, classes=np.array(sorted(set(cat["y"].tolist()))),
             preproc_version=pp.PREPROC_VERSION, features_version=fx.FEATURES_VERSION,
             onset_version=od.ONSET_VERSION, dataset_version=DATASET_VERSION, fs=pp.FS, win_s=a.win,
             used_sc=pp.USED_SC, gate_max_miss=a.max_miss, gate_max_gap=a.max_gap, synthetic=False)
    with open(a.features / f"features_{tag}.csv", "w", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(["session_id", "subject", "take_id", "activity_label", "window_label", "position", "t_start",
                     "rx1_miss", "rx2_miss", "source", "kind"] + names)
        wr.writerows(feats)
    for path, rows in ((a.processed / f"index_{tag}.csv", take_rows),
                       (a.processed / f"windows_{tag}_index.csv", win_rows),
                       (a.processed / "onsets.csv", onset_rows)):
        with open(path, "w", newline="") as fh:
            wr = csv.DictWriter(fh, fieldnames=list(rows[0]))
            wr.writeheader()
            wr.writerows(rows)
    if tag == "3s":
        shutil.copy(a.processed / "index_3s.csv", a.processed / "index.csv")
    cnt = {c: int((cat["y"] == c).sum()) for c in sorted(set(cat["y"].tolist()))}
    print(f"\nwindows_{tag}.npz: X {cat['X'].shape}, labels {cnt}")
    print(f"takes {len(take_rows)}; candidates {sum(r['candidates'] for r in take_rows)}, kept {sum(r['kept'] for r in take_rows)}, "
          f"gate-rejected {sum(r['rejected_gate'] for r in take_rows)}, dropped by labelling {sum(r['dropped_label'] for r in take_rows)}")
    print(f"done in {time.time() - t0:.0f} s -> {a.processed}, {a.features}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
