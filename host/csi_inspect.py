#!/usr/bin/env python3
"""Phase 5 inspection of a saved run (host/rx_check.py --save DIR).

Makes three figures and a report in results/signal/<session_id>/ (default; see resolve_out):
  1_heatmap.png   amplitude over time x sub-carrier for each receiver
                  (raw dB, then relative to the static channel) + RSSI
  2_channel.png   channel shape: mean amplitude per sub-carrier, empty (null)
                  sub-carriers, pilots, L-LTF vs HT-LTF, raw phase of a few packets
  3_quality.png   packet rate, gaps, RSSI vs CSI power, gain-change candidates
  report.json     the numbers behind the figures

Usage:
    python3 host/csi_inspect.py data/raw/<session_id>               # -> results/signal/<session_id>/
    python3 host/csi_inspect.py ~/csi_runs/e0_swap --t0 25 --t1 37  # -> results/signal/e0_swap_t25-37/
    python3 host/csi_inspect.py RUN --out some/folder --export      # also save decoded .npz

Time axis = TX clock (tx_time_us carried in every packet), so RX1 and RX2 line up.
Nothing is uploaded. Output is never written inside data/raw (raw data is read-only):
an --out path inside any data/raw folder is refused.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import csiwire as cw  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_ROOT = ROOT / "results" / "signal"

EXPECTED_HZ = 200.0
BIN_S = 0.05                 # heatmap time bin (10 packets at 200 Hz)
GAP_LIMIT_MS = 100.0         # D-012: gaps above this would be a problem
STEP_DB = 2.0                # power step that counts as a step
STEP_WIN = 20                # packets on each side when looking for steps
NULL_FRACTION = 0.15         # mean amplitude below 15 % of the typical level -> empty carrier


# ----------------------------------------------------------------------------- analysis
def prepare(rec: cw.Recording):
    """Keep our TX's packets, pick the longest TX boot segment, decode to complex."""
    h = rec.hdr
    ok = ((h["flags"] & cw.F_SEQ_VALID) != 0) & ((h["flags"] & cw.F_RADIO_MISMATCH) == 0)
    h, raw = h[ok], rec.csi_raw[ok]
    segs = cw.tx_segments(h["seq"]) if len(h) else []
    note = None
    if len(segs) > 1:
        note = f"TX rebooted during the run ({len(segs)} segments); using the longest"
    if segs:
        s = max(segs, key=lambda x: x.stop - x.start)
        h, raw = h[s], raw[s]
    lltf, ht = cw.to_complex(raw, h)
    return dict(name=rec.name, rec=rec, hdr=h, lltf=lltf, ht=ht, note=note,
                dropped_not_ours=int((~ok).sum()))


def find_nulls(mean_amp: np.ndarray) -> np.ndarray:
    """Indices whose mean amplitude is far below the typical (upper-half median) level."""
    finite = mean_amp[np.isfinite(mean_amp)]
    if finite.size == 0:
        return np.arange(len(mean_amp))
    typical = np.median(np.sort(finite)[finite.size // 2:])
    return np.flatnonzero(~(mean_amp >= NULL_FRACTION * typical))


def db(x):
    with np.errstate(divide="ignore", invalid="ignore"):
        return 20 * np.log10(x)


def steps(x: np.ndarray, thr: float, win: int = STEP_WIN):
    """Positions where median(after) - median(before) exceeds thr; one per event."""
    n = len(x)
    if n < 2 * win + 1:
        return np.zeros(0, int), np.zeros(0)
    from numpy.lib.stride_tricks import sliding_window_view
    w = sliding_window_view(x, win)
    med = np.median(w, axis=1)                    # med[i] = median(x[i:i+win])
    d = med[win:] - med[:-win]                    # after(i+win..) - before(i..)
    idx = np.arange(len(d)) + win
    big = np.flatnonzero(np.abs(d) > thr)
    picks = []
    for b in big:                                 # keep the strongest point of each run
        if picks and b - picks[-1] < win:
            if abs(d[b]) > abs(d[picks[-1]]):
                picks[-1] = b
            continue
        picks.append(b)
    picks = np.array(picks, int)
    return idx[picks], d[picks]


def analyse(p: dict, t_origin_us: int, t0: float | None, t1: float | None):
    h, ht, lltf = p["hdr"], p["ht"], p["lltf"]
    t = (h["tx_time_us"].astype(np.int64) - t_origin_us) / 1e6
    keep = np.ones(len(t), bool)
    if t0 is not None:
        keep &= t >= t0
    if t1 is not None:
        keep &= t <= t1
    h, ht, lltf, t = h[keep], ht[keep], lltf[keep], t[keep]
    p.update(hdr=h, ht=ht, lltf=lltf, t=t)
    n = len(t)
    r = dict(receiver=p["name"], records=int(n), note=p["note"],
             dropped_not_our_tx=p["dropped_not_ours"],
             crc_rejected_frames=p["rec"].crc_errors,
             other_csi_len=p["rec"].other_len)
    if n < 10:
        r["error"] = "too few records"
        return r

    seq = h["seq"].astype(np.int64)
    span = seq[-1] - seq[0] + 1
    dt_ms = np.diff(t) * 1e3
    r.update(
        duration_s=round(float(t[-1] - t[0]), 2),
        rate_hz=round(float((n - 1) / (t[-1] - t[0])), 1),
        loss_pct=round(100 * (1 - n / span), 2),
        duplicates=int((np.diff(seq) == 0).sum()),
        gap_ms_max=round(float(dt_ms.max()), 1),
        gaps_over_20ms=int((dt_ms > 20).sum()),
        gaps_over_limit=int((dt_ms > GAP_LIMIT_MS).sum()),
        ht40_pct=round(100 * float(np.mean(h["cwb"] == 1)), 2),
        ht_sig_pct=round(100 * float(np.mean(h["sig_mode"] == 1)), 2),
        first_word_invalid_pct=round(100 * float(np.mean(h["flags"] & cw.F_FIRST_WORD_INVALID != 0)), 2),
        rssi_dbm=dict(median=float(np.median(h["rssi"])), p5=float(np.percentile(h["rssi"], 5)),
                      p95=float(np.percentile(h["rssi"], 95))),
        noise_floor_dbm_median=float(np.median(h["noise_floor"])),
    )

    amp = np.abs(ht)
    mean_amp = np.nanmean(amp, axis=0)
    nulls = find_nulls(mean_amp)
    used = np.setdiff1d(np.arange(cw.N_HTLTF), nulls)
    p.update(amp=amp, mean_amp=mean_amp, used=used, nulls=nulls)
    sc = cw.HTLTF_SC
    r["htltf_null_subcarriers"] = compress(sc[nulls])
    r["htltf_used_count"] = int(len(used))
    r["htltf_matches_80211n_ht40"] = bool(np.array_equal(np.sort(sc[used]), cw.HT40_EXPECTED_USED))

    lamp = np.nanmean(np.abs(lltf), axis=0)
    lnull = find_nulls(lamp)
    p.update(lamp=lamp, lnull=lnull)
    r["lltf_null_bins"] = compress(cw.LLTF_INDEX[lnull])

    # Total CSI power per packet (dB), over the used carriers only.
    pw = 10 * np.log10(np.nanmean(amp[:, used] ** 2, axis=1))
    p["csi_pw"] = pw
    rssi = h["rssi"].astype(float)
    si, sd = steps(pw, STEP_DB)
    ri = np.searchsorted(np.arange(n), si)
    # RSSI change across the same window: if CSI power jumps but RSSI does not
    # (or the other way round), the receiver gain probably changed (AGC step).
    rd = np.array([np.median(rssi[i:i + STEP_WIN]) - np.median(rssi[max(0, i - STEP_WIN):i])
                   for i in ri]) if len(ri) else np.zeros(0)
    gain = np.abs(sd - rd) > STEP_DB
    p.update(step_idx=si, step_gain=gain)
    r["csi_power_steps"] = [dict(t_s=round(float(t[i]), 2), csi_db=round(float(a), 1),
                                 rssi_db=round(float(b), 1), gain_change_candidate=bool(g))
                            for i, a, b, g in zip(si, sd, rd, gain)]
    r["gain_change_candidates"] = int(gain.sum())
    with np.errstate(invalid="ignore"):
        r["corr_csi_power_vs_rssi"] = round(float(np.corrcoef(pw, rssi)[0, 1]), 3) if np.std(rssi) > 0 else None
    return r


def compress(ix) -> str:
    """[-64,-63,...,-59,0,1] -> '-64..-59, 0..1'."""
    ix = sorted(int(i) for i in ix)
    if not ix:
        return ""
    out, a, b = [], ix[0], ix[0]
    for i in ix[1:]:
        if i == b + 1:
            b = i
            continue
        out.append(f"{a}" if a == b else f"{a}..{b}")
        a = b = i
    out.append(f"{a}" if a == b else f"{a}..{b}")
    return ", ".join(out)


# Which HT40 sub-carrier does L-LTF bin k sit on? The ESP-IDF table only says "0~63".
LLTF_HYPOTHESES = {
    "bin k = HT40 sub-carrier k (upper 20 MHz)": lambda k: k,
    "bin k = HT40 sub-carrier k-64 (lower 20 MHz)": lambda k: k - 64,
    "FFT order around the upper-20 MHz centre (+32)": lambda k: 32 + np.where(k < 32, k, k - 64),
    "FFT order around the lower-20 MHz centre (-32)": lambda k: -32 + np.where(k < 32, k, k - 64),
}


def lltf_mapping(p: dict):
    """Correlate the mean L-LTF amplitude profile with HT-LTF under each hypothesis."""
    k = cw.LLTF_INDEX
    lvalid = np.setdiff1d(np.arange(64), p["lnull"])
    ht_db = db(p["mean_amp"])
    used_sc = set(cw.HTLTF_SC[p["used"]].tolist())
    out = {}
    for name, f in LLTF_HYPOTHESES.items():
        sc = f(k)
        pairs = [(i, int(s)) for i, s in zip(lvalid, sc[lvalid]) if int(s) in used_sc]
        if len(pairs) < 10:
            out[name] = dict(overlap=len(pairs), r=None)
            continue
        li = np.array([a for a, _ in pairs])
        hi = np.array([b for _, b in pairs]) + 64
        a, b = db(p["lamp"][li]), ht_db[hi]
        out[name] = dict(overlap=len(pairs), r=round(float(np.corrcoef(a, b)[0, 1]), 3))
    ranked = sorted((v["r"], n) for n, v in out.items() if v["r"] is not None)
    verdict = "inconclusive"
    if ranked:
        best_r, best = ranked[-1]
        second = ranked[-2][0] if len(ranked) > 1 else -1
        if best_r >= 0.8 and best_r - second >= 0.1:
            verdict = best
    return out, verdict


# ----------------------------------------------------------------------------- figures
def binned(t, x, t_lo, t_hi, bin_s=BIN_S):
    """Average rows of x into time bins, ignoring NaN; empty bins (gaps) become NaN rows."""
    edges = np.arange(t_lo, t_hi + bin_s, bin_s)
    idx = np.clip(np.digitize(t, edges) - 1, 0, len(edges) - 2)
    fin = np.isfinite(x)
    sums = np.zeros((len(edges) - 1, x.shape[1]))
    cnts = np.zeros_like(sums)
    np.add.at(sums, idx, np.where(fin, x, 0))
    np.add.at(cnts, idx, fin)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = (sums / cnts).astype(np.float32)
    return out, edges


def smooth(t, x, bin_s=0.25):
    """Mean of x in bin_s time bins -> (bin centres, means), for readable traces."""
    b, e = binned(t, x[:, None].astype(float), t[0], t[-1], bin_s)
    return (e[:-1] + bin_s / 2), b[:, 0]


def cmap_grey(name):
    import matplotlib
    c = matplotlib.colormaps[name].copy()
    c.set_bad("0.82")                    # NaN (empty carrier or no packets) -> light grey
    return c


def fig_heatmap(P, out: Path, plt):
    t_lo = min(p["t"][0] for p in P)
    t_hi = max(p["t"][-1] for p in P)
    fig, ax = plt.subplots(3, len(P), figsize=(7 * len(P), 10), squeeze=False,
                           gridspec_kw=dict(height_ratios=[3, 3, 1.2]), sharex=True)
    for c, p in enumerate(P):
        sc = cw.HTLTF_SC
        amp = p["amp"].copy()
        amp[:, p["nulls"]] = np.nan
        raw_db = db(amp)
        raw_db[~np.isfinite(raw_db)] = np.nan
        # Relative view: remove the per-packet common gain, then the static channel.
        rel = amp / np.nanmean(amp[:, p["used"]], axis=1, keepdims=True)
        rel = db(rel / np.nanmedian(rel, axis=0, keepdims=True))
        rel[~np.isfinite(rel)] = np.nan
        ext = [sc[0] - 0.5, sc[-1] + 0.5, t_hi, t_lo]
        for r_, (data, title, kw) in enumerate([
            (raw_db, "|H| in dB (raw, includes receiver gain)", dict(cmap=cmap_grey("viridis"))),
            (rel, "|H| relative to the static channel, dB (gain removed per packet)",
             dict(cmap=cmap_grey("RdBu_r"), vmin=-3, vmax=3)),
        ]):
            b, _ = binned(p["t"], data, t_lo, t_hi)
            if "vmin" not in kw:
                kw.update(vmin=np.nanpercentile(b, 2), vmax=np.nanpercentile(b, 98))
            im = ax[r_, c].imshow(b, aspect="auto", extent=ext, interpolation="nearest", **kw)
            ax[r_, c].set_title(f"{p['name']}: {title}", fontsize=10)
            ax[r_, c].set_ylabel("time (s, TX clock)")
            fig.colorbar(im, ax=ax[r_, c], pad=0.01)
        # Third row: RSSI vs time, drawn horizontally under the heatmaps would need a
        # different x axis, so give it its own axes.
        ax[2, c].remove()
        a = fig.add_subplot(3, len(P), 2 * len(P) + c + 1)
        a.plot(p["t"], p["hdr"]["rssi"], lw=0.3, color="0.8")
        a.plot(*smooth(p["t"], p["hdr"]["rssi"]), lw=1, color="#333", label="0.25 s mean")
        a.legend(fontsize=8, loc="lower right")
        a.set_xlim(t_lo, t_hi)
        a.set_xlabel("time (s)")
        a.set_ylabel("RSSI dBm")
        a.set_title(f"{p['name']}: RSSI", fontsize=10)
        for r_ in range(2):
            ax[r_, c].set_xlabel("HT-LTF sub-carrier")
            ax[r_, c].tick_params(labelbottom=True)
    fig.suptitle("1. CSI amplitude over time (grey rows = no packets in that 50 ms bin; "
                 "grey columns = empty sub-carriers)", fontsize=11)
    fig.tight_layout()
    fig.savefig(out, dpi=110)
    plt.close(fig)


def fig_channel(P, mapping, out: Path, plt):
    fig, ax = plt.subplots(4, 1, figsize=(12, 15))
    sc = cw.HTLTF_SC
    colors = ["#1f77b4", "#d62728", "#2ca02c"]
    for i, p in enumerate(P):
        a = p["amp"]
        lo, hi = np.nanpercentile(a, 10, axis=0), np.nanpercentile(a, 90, axis=0)
        ax[0].fill_between(sc, db(lo), db(hi), color=colors[i], alpha=0.15)
        ax[0].plot(sc, db(p["mean_amp"]), color=colors[i], lw=1.2, label=f"{p['name']} mean (10-90 % band)")
        ax[0].plot(sc[p["nulls"]], db(np.maximum(p["mean_amp"][p["nulls"]], 0.3)), "x",
                   color=colors[i], ms=6, label=f"{p['name']} empty ({len(p['nulls'])})")
        ax[1].plot(cw.LLTF_INDEX, db(p["lamp"]), color=colors[i], lw=1.2, label=p["name"])
        ax[1].plot(cw.LLTF_INDEX[p["lnull"]], db(np.maximum(p["lamp"][p["lnull"]], 0.3)), "x",
                   color=colors[i], ms=6)
    for pl in cw.HT40_PILOTS:
        ax[0].axvline(pl, color="k", ls=":", lw=0.8)
    ax[0].axvspan(-64.5, -58.5, color="0.85", zorder=0)
    ax[0].axvspan(58.5, 63.5, color="0.85", zorder=0)
    ax[0].axvspan(-1.5, 1.5, color="0.85", zorder=0)
    ax[0].set_title("HT-LTF: mean |H| per sub-carrier. Grey = empty in the 802.11n HT40 standard "
                    "(edges, DC -1..+1); dotted = pilots ±11, ±25, ±53", fontsize=10)
    ax[0].set_xlabel("sub-carrier index (-64..63, 312.5 kHz apart)")
    ax[0].set_ylabel("dB")
    ax[0].legend(fontsize=8, ncol=2)
    ax[1].set_title("L-LTF: mean |H| per buffer bin (ESP-IDF calls these indices 0..63)", fontsize=10)
    ax[1].set_xlabel("L-LTF bin")
    ax[1].set_ylabel("dB")
    ax[1].legend(fontsize=8)

    # L-LTF vs HT-LTF on the same axis, using the best-fitting mapping (first receiver).
    p = P[0]
    res, verdict = mapping[p["name"]]
    name = verdict if verdict != "inconclusive" else max(
        (v["r"] if v["r"] is not None else -9, n) for n, v in res.items())[1]
    f = LLTF_HYPOTHESES[name]
    lsc = f(cw.LLTF_INDEX)
    lv = np.setdiff1d(np.arange(64), p["lnull"])
    hu = p["used"]
    ref = np.nanmedian(db(p["mean_amp"][hu]))
    ax[2].plot(sc[hu], db(p["mean_amp"][hu]) - ref, ".-", lw=0.8, ms=3, label="HT-LTF")
    ax[2].plot(lsc[lv], db(p["lamp"][lv]) - np.nanmedian(db(p["lamp"][lv])), ".-", lw=0.8, ms=3,
               label=f"L-LTF placed by: {name}")
    txt = "\n".join(f"r = {v['r']}  (overlap {v['overlap']})  {n}" for n, v in res.items())
    ax[2].text(0.01, 0.02, txt + f"\nverdict: {verdict}", transform=ax[2].transAxes, fontsize=8,
               va="bottom", family="monospace", bbox=dict(fc="white", alpha=0.8))
    ax[2].set_xlim(-64, 64)
    ax[2].set_title(f"{p['name']}: L-LTF vs HT-LTF shape (each relative to its own median)", fontsize=10)
    ax[2].set_xlabel("HT40 sub-carrier")
    ax[2].set_ylabel("dB")
    ax[2].legend(fontsize=8, loc="upper right")

    # Raw phase of a few consecutive packets: shows why phase needs cleaning later.
    k0 = len(p["t"]) // 2
    for j in range(5):
        z = p["ht"][k0 + j, hu]
        ax[3].plot(sc[hu], np.unwrap(np.angle(z)), lw=0.9, label=f"packet {k0 + j}")
    ax[3].set_title(f"{p['name']}: raw HT-LTF phase (unwrapped) of 5 consecutive packets, 5 ms apart. "
                    "Different slopes/offsets = timing and carrier offsets, not people", fontsize=10)
    ax[3].set_xlabel("HT40 sub-carrier")
    ax[3].set_ylabel("rad")
    ax[3].legend(fontsize=8)
    fig.suptitle("2. Channel shape", fontsize=11)
    fig.tight_layout()
    fig.savefig(out, dpi=110)
    plt.close(fig)


def fig_quality(P, out: Path, plt):
    fig, ax = plt.subplots(4, len(P), figsize=(7 * len(P), 13), squeeze=False)
    for c, p in enumerate(P):
        t, h = p["t"], p["hdr"]
        sec = np.floor(t).astype(int)
        s0 = sec.min()
        cnt = np.bincount(sec - s0)
        x = np.arange(len(cnt)) + s0
        ax[0, c].step(x, cnt, where="post", lw=1)
        ax[0, c].axhline(EXPECTED_HZ, color="g", ls="--", lw=0.8, label="TX rate 200/s")
        ax[0, c].axhline(190, color="r", ls=":", lw=0.8, label="E0 gate 190/s")
        ax[0, c].set_ylim(0, 215)
        ax[0, c].set_title(f"{p['name']}: packets per second (first/last second partial)", fontsize=10)
        ax[0, c].set_xlabel("time (s)")
        ax[0, c].legend(fontsize=8, loc="lower right")

        dt = np.diff(t) * 1e3
        bins = np.concatenate([np.arange(0, 30, 1), np.logspace(np.log10(30), np.log10(max(200, dt.max() + 1)), 15)])
        ax[1, c].hist(dt, bins=bins, log=True, color="#777")
        ax[1, c].axvline(5, color="g", ls="--", lw=0.8, label="5 ms = no loss")
        ax[1, c].axvline(GAP_LIMIT_MS, color="r", ls=":", lw=0.8, label="100 ms limit (D-012)")
        ax[1, c].set_xscale("symlog", linthresh=30)
        ax[1, c].set_title(f"{p['name']}: time between received packets (max {dt.max():.0f} ms)", fontsize=10)
        ax[1, c].set_xlabel("ms")
        ax[1, c].set_ylabel("count")
        ax[1, c].legend(fontsize=8)

        rssi = h["rssi"].astype(float)
        pw = p["csi_pw"]
        off = np.median(rssi) - np.median(pw)
        ax[2, c].plot(*smooth(t, rssi), lw=1, label="RSSI (dBm), 0.25 s mean", color="#333")
        ax[2, c].plot(*smooth(t, pw + off), lw=1, label=f"CSI power (dB, shifted {off:+.0f}), 0.25 s mean",
                      color="#1f77b4")
        for i, g in zip(p["step_idx"], p["step_gain"]):
            ax[2, c].axvline(t[i], color="r" if g else "orange", lw=1, alpha=0.7)
        ax[2, c].set_title(f"{p['name']}: RSSI and CSI power; lines = CSI power steps > {STEP_DB:g} dB "
                           "(red = RSSI disagrees: gain-change candidate)", fontsize=9)
        ax[2, c].set_xlabel("time (s)")
        ax[2, c].legend(fontsize=8)

        sct = ax[3, c].scatter(rssi + np.random.default_rng(0).uniform(-0.3, 0.3, len(rssi)), pw,
                               c=t, s=2, cmap="plasma")
        fig.colorbar(sct, ax=ax[3, c], label="time (s)")
        ax[3, c].set_title(f"{p['name']}: CSI power vs RSSI (RSSI jittered ±0.3 to show density)", fontsize=10)
        ax[3, c].set_xlabel("RSSI dBm")
        ax[3, c].set_ylabel("CSI power dB")
    fig.suptitle("3. Quality checks", fontsize=11)
    fig.tight_layout()
    fig.savefig(out, dpi=110)
    plt.close(fig)


# ----------------------------------------------------------------------------- output folder
def inside_raw(path: Path) -> bool:
    """True if path (after resolving symlinks) is inside a data/raw folder, including _rejected."""
    parts = Path(path).expanduser().resolve().parts
    return any(a == "data" and b == "raw" for a, b in zip(parts, parts[1:]))


def resolve_out(run: Path, out: Path | None, t0: float | None, t1: float | None,
                out_root: Path = DEFAULT_OUT_ROOT) -> Path:
    """Output folder: --out if given, else <out_root>/<session_id>[_t<t0>-<t1>].

    session_id comes from RUN/meta.json if present, else the RUN folder name.
    Raises ValueError for any path inside data/raw.
    """
    if out is None:
        sid = Path(run).resolve().name
        meta = Path(run) / "meta.json"
        if meta.exists():
            try:
                sid = json.loads(meta.read_text()).get("session_id") or sid
            except ValueError:
                pass
        if t0 is not None or t1 is not None:
            sid += f"_t{t0 if t0 is not None else 'start'}-{t1 if t1 is not None else 'end'}"
        out = Path(out_root) / sid
    if inside_raw(out):
        raise ValueError(f"refusing to write inside data/raw (raw data is read-only): {out}")
    return Path(out)


# ----------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", type=Path, help="folder made by rx_check.py --save (contains RX1.bin / RX2.bin)")
    ap.add_argument("--t0", type=float, help="start time (s) for the window")
    ap.add_argument("--t1", type=float, help="end time (s) for the window")
    ap.add_argument("--out", type=Path, help="output folder (default results/signal/<session_id>[_tT0-T1]; never inside data/raw)")
    ap.add_argument("--export", action="store_true", help="also write decoded arrays (.npz) for later phases")
    a = ap.parse_args()
    import warnings
    warnings.filterwarnings("ignore", category=RuntimeWarning)   # NaN columns are expected

    try:
        out = resolve_out(a.run, a.out, a.t0, a.t1)
    except ValueError as e:
        print(f"ERROR: {e}")
        return 2

    files = sorted(a.run.glob("RX*.bin"))
    if not files:
        print(f"no RX*.bin in {a.run}")
        return 1
    P = []
    for f in files:
        rec = cw.load(f)
        print(f"{rec.name}: {rec.bytes_total} bytes, {rec.n} CSI records (384 B), "
              f"{rec.crc_errors} CRC-rejected frames, other csi_len: {rec.other_len or 'none'}")
        if rec.n:
            P.append(prepare(rec))
    P = [p for p in P if len(p["hdr"])]
    if not P:
        print("no usable CSI records")
        return 1

    t_origin = min(int(p["hdr"]["tx_time_us"][0]) for p in P)
    report = dict(run=str(a.run), window_s=[a.t0, a.t1], receivers={})
    for p in P:
        report["receivers"][p["name"]] = analyse(p, t_origin, a.t0, a.t1)
    P = [p for p in P if "error" not in report["receivers"][p["name"]]]
    if not P:
        print("too few records in the window")
        return 1
    mapping = {p["name"]: lltf_mapping(p) for p in P}
    for p in P:
        res, verdict = mapping[p["name"]]
        report["receivers"][p["name"]]["lltf_mapping"] = dict(correlations=res, verdict=verdict)

    if len(P) >= 2:
        a_, b_ = P[0], P[1]
        common = np.intersect1d(a_["hdr"]["seq"], b_["hdr"]["seq"])
        union = np.union1d(a_["hdr"]["seq"], b_["hdr"]["seq"])
        report["seen_by_both_pct"] = round(100 * len(common) / len(union), 2)

    out.mkdir(parents=True, exist_ok=True)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig_heatmap(P, out / "1_heatmap.png", plt)
    fig_channel(P, mapping, out / "2_channel.png", plt)
    fig_quality(P, out / "3_quality.png", plt)
    (out / "report.json").write_text(json.dumps(report, indent=2))

    if a.export:
        for p in P:
            np.savez_compressed(out / f"csi_{p['name']}.npz", t=p["t"], hdr=p["hdr"],
                                lltf=p["lltf"], htltf=p["ht"], htltf_sc=cw.HTLTF_SC,
                                htltf_null=p["nulls"])

    # Short text summary
    print()
    for name, r in report["receivers"].items():
        if "error" in r:
            print(f"{name}: {r['error']}")
            continue
        print(f"{name}: {r['records']} pkts over {r['duration_s']} s = {r['rate_hz']}/s, loss {r['loss_pct']} %, "
              f"max gap {r['gap_ms_max']} ms ({r['gaps_over_limit']} over {GAP_LIMIT_MS:g} ms), "
              f"HT40 {r['ht40_pct']} %, RSSI {r['rssi_dbm']['median']:.0f} dBm "
              f"[{r['rssi_dbm']['p5']:.0f}..{r['rssi_dbm']['p95']:.0f}]")
        print(f"   HT-LTF empty sub-carriers: {r['htltf_null_subcarriers']}  "
              f"({r['htltf_used_count']} used; matches 802.11n HT40 layout: {r['htltf_matches_80211n_ht40']})")
        print(f"   L-LTF empty bins: {r['lltf_null_bins']}")
        print(f"   L-LTF placement: {r['lltf_mapping']['verdict']}")
        print(f"   CSI power steps > {STEP_DB:g} dB: {len(r['csi_power_steps'])}, "
              f"gain-change candidates: {r['gain_change_candidates']}, "
              f"corr(CSI power, RSSI) = {r['corr_csi_power_vs_rssi']}")
        if r["note"]:
            print(f"   note: {r['note']}")
    if "seen_by_both_pct" in report:
        print(f"seen by both: {report['seen_by_both_pct']} %")
    print(f"\nfigures and report.json in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
