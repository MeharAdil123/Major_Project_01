#!/usr/bin/env python3
"""Diagnose the live-test failure with 6 takes recorded on 2026-10-23 (data/live_library/diag_takes).

    python3 scripts/phase5_diag_analysis.py > results/phase5/live_library/diag_analysis.log

0. Receiver identity: MAC in the HELLO frames of RX1.bin / RX2.bin (today and a 22 Oct take).
1. OFFLINE pipeline (preprocess v2, f2, final models) on today's takes: per take, window predictions with the
   gate, plus the fall-alarm rule replayed on a 0.5 s stream. Reference: LOSO predictions on 22 Oct windows of
   the same activity and position (results/phase4/track_a/*/..._dynamic__4s.pred.csv), i.e. what a NEW person
   got in testing (the final models saw 22 Oct, so their 22 Oct predictions would be in-sample).
2. Today vs 22 Oct for the same activity and position: RSSI, loss (meta check), per-carrier amplitude profile
   (gain-normalised, dB; RMS difference vs the 22 Oct takes, with the 22 Oct take-to-take spread for scale),
   and the dynamic features the models use (today's median as a percentile of the 22 Oct distribution).
"""
import collections
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from host import csiwire as cw  # noqa: E402
from ml import features as fx  # noqa: E402
from ml.predict import Predictor  # noqa: E402
from pipeline import build_dataset as bd  # noqa: E402
from pipeline import labels as lb  # noqa: E402
from pipeline import onset as od  # noqa: E402
from pipeline import preprocess as pp  # noqa: E402

DIAG = ROOT / "data" / "live_library" / "diag_takes"
RAW = ROOT / "data" / "raw"
WIN = 4.0
KEY = ["rx1_motion_mean", "rx2_motion_mean", "rx1_motion_max", "rx2_motion_max", "rx1_sd_mean", "rx2_sd_mean",
       "rx1_pc1_logpower", "rx2_pc1_logpower", "rx1_pc1_frac_1_3Hz", "rx2_pc1_frac_1_3Hz", "rx1_ph_cvar_w",
       "rx2_ph_cvar_w", "rx1_sc_corr", "rx2_sc_corr", "xrx_motion_corr"]


def hello_macs(folder):
    out = {}
    for r in (1, 2):
        rec = cw.load(folder / f"RX{r}.bin")
        macs = {h.get("mac") for h in rec.hello if isinstance(h, dict)}
        ids = set(np.unique(rec.hdr["rx_id"]).tolist()) if rec.n else set()
        out[f"RX{r}.bin"] = dict(mac=sorted(m for m in macs if m), rx_id_in_header=sorted(ids))
    return out


def windows(folder, meta):
    _, per_rx = bd.load_take(folder)
    g = pp.build_grid(per_rx)
    first = min(int(d["seq"][0]) for d in per_rx.values())
    off = (g["seq0"] - first) / pp.FS_IN
    span = int(WIN * pp.FS_IN)
    L = g["amp"].shape[1]
    starts = list(range(0, L - span + 1, int(0.5 * pp.FS_IN)))           # live-like stream, hop 0.5 s
    w = pp.cut_windows(g, starts, WIN)
    onset = None
    if meta["kind"] == "event":
        t, m = od.motion_signal(g)
        d = od.detect(t, m, meta["cue_s"] - off)
        onset = dict(detected=d["detected"], onset=d["onset"] + off, end=d["end"] + off, early=d["early"],
                     short=d["short"], peak_ratio=d["peak_ratio"])
    return g, w, w["start_pkt"] / pp.FS_IN + off, onset


def alarm_replay(t_end, p, ok, a):
    votes, last, out = collections.deque(maxlen=a["n"]), -1e9, []
    for t, x, g in zip(t_end, p, ok):
        if not g:
            continue
        votes.append(x >= a["theta"])
        if sum(votes) >= a["k"] and t - last > a["cooldown_s"]:
            out.append(round(float(t), 1))
            last = t
    return out


def main():
    pred = Predictor(ROOT / "models")
    feats22 = pd.read_csv(ROOT / "data" / "features" / "features_4s.csv")
    takes = sorted(p.parent for p in DIAG.glob("*/meta.json") if not p.parent.name.startswith("_"))
    print(f"diagnostic takes: {[t.name for t in takes]}\n")

    print("== 0. receiver identity (MAC from HELLO frames; rx_id in each CSI header)")
    print("   today :", json.dumps(hello_macs(takes[0])))
    print("   22 Oct:", json.dumps(hello_macs(RAW / "20261022_S4_T01_stand")))
    print("   expected RX1 28:84:85:85:5E:2C, RX2 28:84:85:48:D7:DC (PROJECT_CONTEXT §2)")

    ref = {t: pd.read_csv(ROOT / "results" / "phase4" / "track_a" / t / f"{m}__dynamic__4s.pred.csv")
           for t, m in (("presence", "logreg"), ("state", "extra_trees"))}
    ref["events"] = pd.read_csv(ROOT / "results" / "phase4" / "ablations" / "events" / "svm_rbf__dynamic__4s.pred.csv")

    print("\n== 1. OFFLINE predictions on today's takes (final models; gate 20 %/100 ms; windows every 0.5 s)")
    summary = {}
    for folder in takes:
        meta = json.loads((folder / "meta.json").read_text())
        g, w, st, onset = windows(folder, meta)
        ok = w["ok"]
        outs = [pred.predict(w["X"][i], w["rssi"][i], w["P"][i]) if ok[i] else None for i in range(len(ok))]
        okouts = [o for o in outs if o]
        labs = collections.Counter(o["label"] for o in okouts)
        evs = collections.Counter(o["event"] for o in okouts if o["event"] != "none")
        pocc = np.array([o["presence_prob"] for o in okouts])
        fall = np.array([o["fall_prob"] if o else 0.0 for o in outs])
        al = alarm_replay(st + WIN, fall, ok, pred.alarm)
        act, pos = meta["activity"], meta["position"]
        # in-interval event windows (event takes)
        ev_txt = ""
        if onset:
            lab_w, src_w = lb.label_windows(dict(meta, session_id=meta["session_id"]), st, WIN, onset)
            in_ev = [o["event"] for o, s in zip(outs, src_w) if o and s == "event"]
            ev_txt = (f" | onset {'%.2f-%.2f s' % (onset['onset'], onset['end']) if onset['detected'] else 'not detected'}; "
                      f"event windows predicted: {dict(collections.Counter(in_ev))}")
        print(f"\n-- {folder.name}  (performed: {act} @ {pos})")
        print(f"   windows {len(ok)}, gate ok {int(ok.sum())}; label (presence x state): {dict(labs.most_common())}; "
              f"P(occupied) median {np.median(pocc):.2f}; events (argmax != none): {dict(evs.most_common())}; "
              f"max P(fall) {fall.max():.2f}; fall alarms at {al}{ev_txt}")
        # LOSO reference on 22 Oct, same activity / position
        if act == "empty":
            r = ref["presence"][(ref["presence"].activity == "empty")]
            print(f"   22 Oct LOSO reference (presence, empty takes): predicted empty in {np.mean(r.pred == 'empty'):.2f} of {len(r)} windows")
        elif meta["kind"] == "state":
            r = ref["state"][(ref["state"].activity == act) & (ref["state"].position == pos)]
            rp = ref["presence"][(ref["presence"].activity == act) & (ref["presence"].position == pos)]
            print(f"   22 Oct LOSO reference ({act}@{pos}): state correct {np.mean(r.pred == act):.2f} of {len(r)} windows; "
                  f"presence 'occupied' {np.mean(rp.pred == 'occupied'):.2f} of {len(rp)}")
        else:
            r = ref["events"][(ref["events"].activity == act) & (ref["events"].position == pos) & (ref["events"].y == act)]
            print(f"   22 Oct LOSO reference ({act}@{pos}, event windows): predicted {act} {np.mean(r.pred == act):.2f} of {len(r)}; "
                  f"top predictions {dict(collections.Counter(r.pred).most_common(3))}")
        summary[folder.name] = dict(activity=act, position=pos, windows=int(len(ok)), gate_ok=int(ok.sum()),
                                    labels=dict(labs), events=dict(evs), p_occupied_median=float(np.median(pocc)),
                                    max_fall=float(fall.max()), alarms=al, onset=onset,
                                    feats=fx.batch_features(w["X"][ok], w["P"][ok], w["rssi"][ok]) if ok.any() else None,
                                    X=w["X"][ok], meta=meta)

    print("\n== 2. today vs 22 Oct, same activity and position")
    names = fx.feature_names()
    z22 = np.load(ROOT / "data" / "processed" / "windows_4s.npz")
    for name, s in summary.items():
        meta, act, pos = s["meta"], s["activity"], s["position"]
        if s["feats"] is None:
            continue
        sel = (feats22.activity_label == act) & (feats22.position == pos) & \
              ((feats22.source == "state") if meta["kind"] == "state" else (feats22.source == "event"))
        if meta["kind"] == "event":       # only today's windows inside the detected action
            o = s["onset"]
            keep = np.ones(len(s["feats"]), bool) if not (o and o["detected"]) else None
        sessions22 = sorted(feats22.loc[sel, "session_id"].unique())
        print(f"\n-- {name} ({act}@{pos}) vs {len(sessions22)} takes / {int(sel.sum())} windows of 22 Oct")
        ck = meta.get("check", {})
        m22 = [json.loads((RAW / sid / "meta.json").read_text())["check"] for sid in sessions22]
        for rx in ("RX1", "RX2"):
            r22 = np.array([c[rx]["rssi_median"] for c in m22])
            l22 = np.array([c[rx]["loss_pct"] for c in m22])
            print(f"   {rx}: RSSI today {ck[rx]['rssi_median']:.0f} dBm vs 22 Oct median {np.median(r22):.0f} [{r22.min():.0f} … {r22.max():.0f}]; "
                  f"loss today {ck[rx]['loss_pct']:.1f} % vs 22 Oct median {np.median(l22):.1f} % [{l22.min():.1f} … {l22.max():.1f}]")
        # static profile: today vs each 22 Oct take of the same activity/position
        prof = lambda X: 20 * np.log10(np.maximum(np.asarray(X, np.float32).mean(axis=(0, 2)), 1e-6))  # noqa: E731
        idx22 = {sid: np.flatnonzero((z22["session_id"] == sid) & np.isin(z22["source"], ["state", "event", "event_pre"]))
                 for sid in sessions22}
        P22 = {sid: prof(z22["X"][ix]) for sid, ix in idx22.items() if len(ix)}
        pt = prof(s["X"])
        d_today = np.array([[np.sqrt(np.mean((pt[r] - p[r]) ** 2)) for r in (0, 1)] for p in P22.values()])
        vals = list(P22.values())
        d_22 = np.array([[np.sqrt(np.mean((vals[i][r] - vals[j][r]) ** 2)) for r in (0, 1)]
                         for i in range(len(vals)) for j in range(i + 1, len(vals))]) if len(vals) > 1 else np.zeros((1, 2))
        print(f"   amplitude profile RMS dB, today vs 22 Oct takes: RX1 median {np.median(d_today[:, 0]):.1f} (min {d_today[:, 0].min():.1f}), "
              f"RX2 median {np.median(d_today[:, 1]):.1f} (min {d_today[:, 1].min():.1f}) | 22 Oct take-to-take: RX1 median "
              f"{np.median(d_22[:, 0]):.1f}, RX2 {np.median(d_22[:, 1]):.1f}")
        F22 = feats22.loc[sel, KEY].to_numpy(float)
        Ft = s["feats"][:, [names.index(k) for k in KEY]]
        cells = []
        for j, k in enumerate(KEY):
            med = np.median(Ft[:, j])
            pr = 100 * np.mean(F22[:, j] < med)
            cells.append(f"{k} {pr:.0f}")
        print("   today's median as percentile of 22 Oct (50 = typical; <5 or >95 = outside): " + ", ".join(cells))
    out = {k: {kk: vv for kk, vv in v.items() if kk not in ("feats", "X", "meta")} for k, v in summary.items()}
    (ROOT / "results" / "phase5" / "live_library" / "diag_summary.json").write_text(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
