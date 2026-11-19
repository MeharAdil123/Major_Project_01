#!/usr/bin/env python3
"""Phase 2 figures (read-only on data/raw; writes results/signal/).

    python3 scripts/phase2_figures.py

  class_<activity>.png        one take per class (results/signal_selection.txt): per RX, gain-normalised
                              amplitude heatmap, sanitised-phase heatmap, motion energy with cue + peak
  phase_raw_vs_sanitised.png  raw phase vs sanitised phase, heatmaps and per-packet profiles
  csi_scaling.png             per-packet CSI power levels (the ~6 dB step) and its flatness over carriers
  body_shadowing.png          RSSI and loss per position and receiver (all 202 takes, from the audit table)
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from pipeline import preprocess as pp  # noqa: E402
from pipeline import build_dataset as bd  # noqa: E402
import phase2_signal as p2  # noqa: E402

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT = ROOT / "results" / "signal"
RAW = ROOT / "data" / "raw"
SC = pp.USED_SC


def take_arrays(sid):
    """Per RX: seq, complex HT-LTF on the 114 used carriers (ours, longest TX segment)."""
    out = {}
    for rx in (1, 2):
        p = p2.load_rx(RAW / sid, rx)
        hu = p["ht"][:, pp.USED_COL]
        ok = np.all(np.isfinite(hu), axis=1)
        out[rx] = dict(seq=p["hdr"]["seq"][ok].astype(np.int64), hu=hu[ok], rssi=p["hdr"]["rssi"][ok])
    return out


def on_grid(seq, vals, seq0, L):
    """Place per-packet rows on a seq grid (missing = NaN)."""
    g = np.full((L,) + vals.shape[1:], np.nan, dtype=float)
    i = seq - seq0
    m = (i >= 0) & (i < L)
    g[i[m]] = vals[m]
    return g


def class_figure(sid, meta):
    d = take_arrays(sid)
    seq0 = min(int(v["seq"][0]) for v in d.values())
    L = max(int(v["seq"][-1]) for v in d.values()) - seq0 + 1
    t = np.arange(L) / pp.FS_IN
    # motion energy exactly as build_dataset (grid over the common seq range, gap filled)
    per_rx = {}
    for rx, v in d.items():
        keep = np.concatenate([[True], np.diff(v["seq"]) > 0])            # strictly increasing seq
        per_rx[rx] = dict(seq=v["seq"][keep], amp=np.abs(v["hu"][keep]).astype(np.float32),
                          rssi=v["rssi"][keep].astype(np.float32))
    grid = pp.build_grid(per_rx)
    tg = (np.arange(grid["amp"].shape[1]) + grid["seq0"] - seq0) / pp.FS_IN
    a = pp.normalise(grid["amp"])
    k = int(0.2 * pp.FS_IN)
    cue = meta.get("cue_s")
    fig = plt.figure(figsize=(15, 9.5))
    gs = fig.add_gridspec(3, 3, width_ratios=[1, 1, 0.03], height_ratios=[1.3, 1.3, 0.8], wspace=0.15)
    ax = np.empty((3, 2), object)
    for r in range(3):
        for c in range(2):
            ax[r, c] = fig.add_subplot(gs[r, c], sharex=ax[0, 0] if (r or c) else None)
    cax = [fig.add_subplot(gs[0, 2]), fig.add_subplot(gs[1, 2])]
    for c, rx in enumerate((1, 2)):
        v = d[rx]
        amp = np.abs(v["hu"])
        amp_n = amp / amp.mean(axis=1, keepdims=True)
        rel = 20 * np.log10(np.maximum(amp_n, 1e-3) / np.median(amp_n, axis=0, keepdims=True).clip(1e-3))
        G = on_grid(v["seq"], rel, seq0, L)
        im = ax[0, c].imshow(G.T, aspect="auto", origin="lower", cmap="RdBu_r", vmin=-6, vmax=6,
                             extent=[0, L / pp.FS_IN, 0, len(SC)])
        ax[0, c].set_title(f"RX{rx}: gain-normalised amplitude, dB rel. to the take median")
        sph = p2.sanitise(v["hu"])
        sph = p2.wrap(sph - np.angle(np.mean(np.exp(1j * sph), axis=0)))
        P = on_grid(v["seq"], sph, seq0, L)
        im2 = ax[1, c].imshow(P.T, aspect="auto", origin="lower", cmap="twilight_shifted", vmin=-np.pi, vmax=np.pi,
                              extent=[0, L / pp.FS_IN, 0, len(SC)])
        ax[1, c].set_title(f"RX{rx}: sanitised phase minus its time mean (rad)")
        for r in (0, 1):
            ax[r, c].set_yticks([0, 28, 56.5, 85, 113], ["-58", "-30", "±2", "+30", "+58"])
            ax[r, c].set_ylabel("sub-carrier")
        e = np.abs(np.diff(a[c], axis=0)).mean(axis=1)
        e = np.convolve(np.concatenate([[e[0]], e]), np.ones(k) / k, mode="same")
        ax[2, c].plot(tg, e, lw=0.8, label=f"RX{rx} motion energy")
        ax[2, c].set_xlabel("time from first packet (s)")
        ax[2, c].set_ylabel("mean |d amp/dt|")
        if cue is not None:
            ax[2, c].axvline(cue, color="k", ls="--", lw=1, label="cue")
            ax[2, c].axvspan(cue, cue + 4, color="0.9", zorder=0, label="peak search")
        ax[2, c].legend(fontsize=7, loc="upper right")
    fig.colorbar(im, cax=cax[0], label="dB")
    fig.colorbar(im2, cax=cax[1], label="rad")
    # peak as found by the dataset builder (both receivers combined)
    if cue is not None:
        e2 = bd.motion_energy(grid)
        lo = int(cue * pp.FS_IN)
        hi = min(len(e2), lo + 4 * pp.FS_IN)
        pk = lo + int(np.argmax(e2[lo:hi]))
        for c in (0, 1):
            ax[2, c].axvline(tg[pk], color="r", lw=1.2)
            ax[2, c].text(tg[pk], ax[2, c].get_ylim()[1] * 0.9, " peak (builder)", color="r", fontsize=7)
    fig.suptitle(f"{meta['activity']} — {sid} (position {meta['position']}, {meta['kind']}, "
                 f"{meta['instruction'][:70]})", fontsize=10)
    fig.savefig(OUT / f"class_{meta['activity']}.png", dpi=110)
    plt.close(fig)


def phase_figure(sid):
    v = take_arrays(sid)[2]
    hu = v["hu"][:2000]
    raw = np.angle(hu)
    unw = np.unwrap(raw, axis=1)
    san = p2.sanitise(hu)
    fig, ax = plt.subplots(2, 3, figsize=(15, 7.5))
    t = (v["seq"][:2000] - v["seq"][0]) / pp.FS_IN
    ax[0, 0].imshow(raw.T, aspect="auto", origin="lower", cmap="twilight", extent=[t[0], t[-1], 0, 114])
    ax[0, 0].set_title("raw phase (rad, wrapped)\nlooks random from packet to packet")
    ax[0, 1].imshow(p2.wrap(san - np.angle(np.mean(np.exp(1j * san), axis=0))).T, aspect="auto", origin="lower",
                    cmap="twilight_shifted", vmin=-np.pi, vmax=np.pi, extent=[t[0], t[-1], 0, 114])
    ax[0, 1].set_title("sanitised phase minus its time mean\n(unwrap across carriers, remove per-packet line)")
    ax[0, 2].plot(t, raw[:, 85], ".", ms=1, label="raw, carrier +30")
    ax[0, 2].plot(t, san[:, 85], ".", ms=1, label="sanitised, carrier +30")
    ax[0, 2].set_title("one carrier over time")
    ax[0, 2].legend(fontsize=7, markerscale=8)
    for i in range(0, 400, 80):
        ax[1, 0].plot(SC, unw[i], lw=0.8)
        ax[1, 1].plot(SC, san[i], lw=0.8)
    ax[1, 0].set_title("unwrapped raw phase of 5 packets:\ndifferent slope (timing offset) and offset (CFO, PLL)")
    ax[1, 1].set_title("same packets after sanitising:\nonly the channel shape is left")
    A = np.stack([SC.astype(float), np.ones(len(SC))], 1)
    coef = np.linalg.lstsq(A, unw.T, rcond=None)[0]
    ax[1, 2].plot(t, coef[0], ".", ms=1)
    ax[1, 2].set_title("removed slope per packet (rad / carrier)")
    for a_ in ax[1, :2]:
        a_.set_xlabel("sub-carrier")
    for a_ in (ax[0, 2], ax[1, 2]):
        a_.set_xlabel("time (s)")
    fig.suptitle(f"Raw vs sanitised phase — RX2, first 10 s of {sid}", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "phase_raw_vs_sanitised.png", dpi=110)
    plt.close(fig)


def scaling_figure(sid):
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
    d = take_arrays(sid)
    for rx, c in ((1, "C0"), (2, "C1")):
        amp = np.abs(d[rx]["hu"])
        pw = 10 * np.log10(np.mean(amp ** 2, axis=1))
        main = np.median(pw[pw > np.percentile(pw, 30)])
        ax[0].hist(pw - main, bins=np.arange(-10, 4, 0.25), histtype="step", color=c, label=f"RX{rx}", log=True)
        low = pw < main - p2.LOW_STEP_DB
        t = (d[rx]["seq"] - d[rx]["seq"][0]) / pp.FS_IN
        ax[1].plot(t, pw - main, ".", ms=1, color=c, label=f"RX{rx}")
        if low.sum() >= 5:
            r = 20 * np.log10(amp[low].mean(0) / amp[~low].mean(0))
            ax[2].plot(SC, r, color=c, label=f"RX{rx} ({low.sum()} low packets)")
    ax[0].set_title("per-packet CSI power rel. to main level")
    ax[0].set_xlabel("dB")
    ax[0].legend()
    ax[1].set_title("over time")
    ax[1].set_xlabel("time (s)")
    ax[1].set_ylabel("dB")
    ax[2].axhline(-6.02, color="k", ls=":", lw=1, label="-6.02 dB (amplitude / 2)")
    ax[2].set_title("low / main mean amplitude per carrier")
    ax[2].set_xlabel("sub-carrier")
    ax[2].set_ylabel("dB")
    ax[2].legend(fontsize=7)
    fig.suptitle(f"CSI scaling steps — {sid}", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "csi_scaling.png", dpi=110)
    plt.close(fig)


def shadowing_figure():
    rows = list(csv.DictReader(open(ROOT / "results" / "audit" / "raw_takes_all.csv")))
    order = ["none", "C", "B", "A", "M", "path1", "path2", "free"]
    fig, ax = plt.subplots(2, 2, figsize=(13, 7), sharex=True)
    for c, rx in enumerate(("RX1", "RX2")):
        for r, (key, lab) in enumerate(((f"{rx}_rssi_med", "RSSI median (dBm)"), (f"{rx}_loss_pct", "loss (%)"))):
            data = [[float(x[key]) for x in rows if x["position"] == p] for p in order]
            ax[r, c].boxplot(data, tick_labels=order, showfliers=True)
            for i, dd in enumerate(data):
                ax[r, c].plot(np.full(len(dd), i + 1) + np.random.default_rng(i).uniform(-.15, .15, len(dd)), dd,
                              ".", ms=3, alpha=.5, color="C0")
            ax[r, c].set_title(f"{rx}: {lab}")
            ax[r, c].grid(alpha=.3)
    fig.suptitle("Body shadowing by position (202 takes; one point per take; position map: config/position_map.yaml)", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "body_shadowing.png", dpi=110)
    plt.close(fig)


def main():
    sel = [l.split() for l in (ROOT / "results" / "signal_selection.txt").read_text().splitlines() if l.strip()]
    for act, sid, *_ in sel:
        meta = json.loads((RAW / sid / "meta.json").read_text())
        class_figure(sid, meta)
        print("class figure", act, sid, flush=True)
    phase_figure("20261022_S6_E21_fall")
    scaling_figure("20261022_S5_T16_walk")
    shadowing_figure()
    print("figures in", OUT)


if __name__ == "__main__":
    main()
