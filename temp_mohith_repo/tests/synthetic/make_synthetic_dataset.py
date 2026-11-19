#!/usr/bin/env python3
"""Generate a SYNTHETIC dataset in Format 1 (data/raw/<session>/RX1.bin, RX2.bin, meta.json).

For developing and testing tracks B, C and D tonight without hardware. The signals come
from a toy multipath model with one "body" reflection whose delay/amplitude depends on the
activity. Results on this data mean NOTHING about real performance; every meta.json says
"synthetic": true and build/train scripts print a warning when they see it.

    python3 -m tests.synthetic.make_synthetic_dataset --out data_synth/raw --subjects 3
"""
from __future__ import annotations

import argparse
import binascii
import csv
import json
import struct
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from host import csiwire as cw  # noqa: E402

SC = np.arange(-64, 64)
F = SC * 312.5e3
HT_USED = np.concatenate([np.arange(-58, -1), np.arange(2, 59)])
L_USED = np.concatenate([np.arange(6, 32), np.arange(33, 59)])
POS_DELAY = {"A": 12e-9, "B": 22e-9, "C": 31e-9, "L": 18e-9, "M": 26e-9, "none": 0,
             "path1": 20e-9, "path2": 25e-9, "free": 22e-9, "-": 20e-9}


def frame(ftype, payload: bytes) -> bytes:
    body = bytes([ftype]) + struct.pack("<H", len(payload)) + payload
    return b"\xA5\x5A" + body + struct.pack("<H", binascii.crc_hqx(body, 0xFFFF))


def body_track(activity, kind, t, cue, pos, rng, subj_scale):
    """Return (delay[n], amp[n]) of the body reflection, or None for an empty room."""
    if activity == "empty":
        return None
    d0 = POS_DELAY.get(pos, 20e-9) + rng.normal(0, 1e-9)
    breath = np.sin(2 * np.pi * rng.uniform(0.2, 0.33) * t)
    a0 = 0.35 * subj_scale
    if kind == "state":
        if activity == "sit":
            return d0 + 0.02e-9 * breath + 0.05e-9 * rng.standard_normal(len(t)).cumsum() / 50, np.full_like(t, a0 * 0.8)
        if activity == "stand":
            sway = np.sin(2 * np.pi * 0.4 * t + rng.uniform(0, 6))
            return d0 + 0.03e-9 * breath + 0.08e-9 * sway, np.full_like(t, a0)
        if activity == "lie":
            return d0 + 0.06e-9 * breath, np.full_like(t, a0 * 0.6)
        if activity == "walk":
            v = rng.uniform(0.8, 1.3)                     # m/s back and forth over ~3 m
            x = 1.5 * np.sin(2 * np.pi * (v / 6.0) * t + rng.uniform(0, 6))
            return d0 + 2 * x / 3e8, a0 * (1 + 0.3 * np.sin(2 * np.pi * 0.9 * t))
    # events: still before the cue, movement after a reaction time, still after
    react = cue + rng.uniform(0.2, 0.6)
    dur = {"fall": 0.9, "sit_down": 1.6, "stand_up": 1.5, "bend_pick": 2.2}[activity]
    s = np.clip((t - react) / dur, 0, 1)
    shape = s if activity != "bend_pick" else np.sin(np.pi * s)
    depth = {"fall": 1.2, "sit_down": 0.45, "stand_up": -0.45, "bend_pick": 0.5}[activity]
    speed_shape = shape ** (2 if activity == "fall" else 1)
    d = d0 + depth * speed_shape * 2 / 3e8 + 0.02e-9 * breath
    amp = a0 * (1 - 0.3 * shape * (activity == "fall"))
    return d, amp


def make_take(folder: Path, meta: dict, rng, subj_scale):
    folder.mkdir(parents=True, exist_ok=True)
    n = int(meta["duration_s"] * 200)
    t = np.arange(n) / 200
    track = body_track(meta["activity"], meta["kind"], t, meta["cue_s"] or 0, meta["position"], rng, subj_scale)
    seq0 = int(rng.integers(1000, 10_000_000))
    for rx_id in (1, 2):
        paths = [(1.0, 0), (0.6, 35e-9 + rx_id * 7e-9), (0.3, 80e-9)]
        H = np.zeros((n, 128), complex)
        for a, tau in paths:
            H += a * np.exp(-2j * np.pi * F * tau)[None, :]
        if track is not None:
            d, amp = track
            d = d + rx_id * 3e-9
            H += amp[:, None] * np.exp(-2j * np.pi * (F[None, :] + 2.462e9) * d[:, None])
        H *= 1 / (1 + (np.abs(SC) / 62) ** 12)
        gain = 25 * 10 ** (rng.normal(0, 0.5) / 20)
        delay = rng.normal(0, 30e-9, n)[:, None]
        cfo = rng.uniform(-np.pi, np.pi, n)[:, None]
        Hm = gain * H * np.exp(1j * (cfo - 2 * np.pi * F[None, :] * delay))
        Hm += rng.normal(0, 0.7, Hm.shape) + 1j * rng.normal(0, 0.7, Hm.shape)
        ht = np.zeros_like(Hm)
        ht[:, HT_USED + 64] = Hm[:, HT_USED + 64]
        lt = np.zeros((n, 64), complex)
        lt[:, L_USED] = Hm[:, L_USED + 64]
        z = np.concatenate([lt, ht[:, 64:], ht[:, :64]], axis=1)
        iq = np.empty((n, 384), np.int8)
        iq[:, 0::2] = np.clip(np.round(z.imag), -128, 127)
        iq[:, 1::2] = np.clip(np.round(z.real), -128, 127)
        rssi = np.round(-50 + 20 * np.log10(np.abs(H[:, 64 + 10]) + 1e-3) + rng.normal(0, 0.6, n)).astype(int)
        drop = rng.random(n) < (0.01 if rx_id == 1 else 0.02)
        out = bytearray(frame(cw.T_HELLO, json.dumps(dict(role="rx", rx_id=rx_id, fw="synthetic")).encode()))
        for i in range(n):
            if drop[i]:
                continue
            seq = seq0 + i
            hdr = cw.HDR.pack(2, rx_id, cw.F_SEQ_VALID, seq, 10_000_000 + seq * 5000, seq * 5000, (seq * 5000) & 0xFFFFFFFF,
                              0xCBD36978, seq & 0xFFF, int(rssi[i]), -92, 20, 0, 1, 0, 1, 11, 2, 0, 32, 384)
            out += frame(cw.T_CSI, hdr + iq[i].tobytes())
        (folder / f"RX{rx_id}.bin").write_bytes(bytes(out))
    (folder / "meta.json").write_text(json.dumps(meta, indent=2))


def read_plan(p):
    with open(p, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["duration_s"] = float(r["duration_s"])
        r["cue_s"] = float(r["cue_s"]) if r["cue_s"] else None
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "data_synth" / "raw")
    ap.add_argument("--subjects", type=int, default=3)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    subj_plan = read_plan(ROOT / "protocol" / "plan_subject.csv")
    empty = read_plan(ROOT / "protocol" / "plan_empty.csv") + read_plan(ROOT / "protocol" / "plan_empty_short.csv") * a.subjects
    jobs = [("none", r, f"{r['take_id']}x{k}") for k, r in enumerate(empty)]
    for s in range(1, a.subjects + 1):
        jobs += [(f"P{s}", r, r["take_id"]) for r in subj_plan]
    scales = {f"P{s}": rng.uniform(0.8, 1.2) for s in range(1, a.subjects + 1)}
    for subj, r, tid in jobs:
        sid = f"SYNTH_{subj}_{tid}_{r['activity']}"
        meta = dict(session_id=sid, protocol="p1", synthetic=True, take_id=tid, kind=r["kind"],
                    activity=r["activity"], position=r["position"], subject=subj, setting="same_room",
                    layout="synthetic", operator_position="O", tx_power_dbm=None,
                    duration_s=r["duration_s"], cue_s=r["cue_s"], start_local=None,
                    instruction=r["say"], valid=True, check={}, notes="SYNTHETIC")
        make_take(a.out / sid, meta, rng, scales.get(subj, 1.0))
        print(sid)
    print(f"wrote {len(jobs)} synthetic takes to {a.out}")


if __name__ == "__main__":
    main()
