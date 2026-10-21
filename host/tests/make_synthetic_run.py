#!/usr/bin/env python3
"""Write a fake run folder (RX1.bin, RX2.bin) in wire protocol v2 to test csi_inspect.py.

The data is SYNTHETIC, made from a simple multipath model. It is only for testing
the software; it says nothing about the real channel.

Built in on purpose, so the tool's output can be checked:
  - 802.11n HT40 layout: HT-LTF used on -58..-2 and +2..+58, L-LTF bins 6..31, 33..58
    (that is the "bin k = sub-carrier k, upper 20 MHz" placement)
  - a moving reflector from 29 s to 33 s (both receivers)
  - RX2: a +4 dB receiver-gain step at 45 s with RSSI unchanged (one gain-change candidate)
  - RX2: one 60 ms gap at 20 s, ~2 % random loss and a few corrupted bytes (CRC rejects)
  - RX1: ~1 % random loss
Usage: python3 make_synthetic_run.py OUTDIR [--seconds 60]
"""
import argparse
import binascii
import json
import struct
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import csiwire as cw  # noqa: E402


def frame(ftype, payload: bytes) -> bytes:
    body = bytes([ftype]) + struct.pack("<H", len(payload)) + payload
    return b"\xA5\x5A" + body + struct.pack("<H", binascii.crc_hqx(body, 0xFFFF))


def channel(sc, t, rng, paths, mover):
    f = sc * 312.5e3
    H = np.zeros(len(sc), complex)
    for a, tau in paths:
        H += a * np.exp(-2j * np.pi * f * tau)
    if mover is not None and 29 <= t <= 33:
        # reflector moving at ~1 m/s: path length changes, so its delay changes
        tau = 20e-9 + (t - 29) * 1.0 / 3e8 * 2
        H += 0.5 * np.exp(-2j * np.pi * (f * tau + 2.462e9 * tau))
    # receive filter roll-off near band edges
    H *= 1 / (1 + (np.abs(sc) / 62) ** 12)
    return H


def make(path: Path, rx_id: int, seconds: float, loss: float, rng, gain_step=None, gap=None,
         corrupt=0):
    paths = [(1.0, 0), (0.6, 35e-9 + rx_id * 7e-9), (0.3, 80e-9)]
    ht_used = np.concatenate([np.arange(-58, -1), np.arange(2, 59)])
    l_used = np.concatenate([np.arange(6, 32), np.arange(33, 59)])
    out = bytearray()
    hello = dict(role="rx", rx_id=rx_id, fw="synthetic", radio_id="0xCBD36978")
    out += frame(cw.T_HELLO, json.dumps(hello).encode())
    n = int(seconds * 200)
    t0_us = 123_456_789
    for seq in range(n):
        t = seq / 200
        if rng.random() < loss or (gap and gap[0] <= t < gap[0] + gap[1]):
            continue
        H = channel(np.arange(-64, 64), t, rng, paths, True)
        delay = rng.normal(0, 30e-9)                     # timing offset -> phase slope
        cfo = rng.uniform(-np.pi, np.pi)                 # random common phase
        g = 25.0 * (10 ** (4 / 20) if gain_step and t >= gain_step else 1)
        sc = np.arange(-64, 64)
        Hm = g * H * np.exp(1j * (cfo - 2 * np.pi * sc * 312.5e3 * delay))
        Hm = Hm + rng.normal(0, 0.7, 128) + 1j * rng.normal(0, 0.7, 128)
        ht = np.zeros(128, complex)
        ht[ht_used + 64] = Hm[ht_used + 64]
        lt = np.zeros(64, complex)
        lt[l_used] = Hm[l_used + 64]                      # bin k = sub-carrier k
        ht_buf = np.concatenate([ht[64:128], ht[0:64]])   # buffer order 0..63, -64..-1
        z = np.concatenate([lt, ht_buf])
        iq = np.empty(384, np.int8)
        iq[0::2] = np.clip(np.round(z.imag), -128, 127)
        iq[1::2] = np.clip(np.round(z.real), -128, 127)
        rssi = int(round(-45 + 20 * np.log10(np.abs(H[64 + 10]) + 1e-3) + rng.normal(0, 0.6)))
        hdr = cw.HDR.pack(2, rx_id, cw.F_SEQ_VALID, seq, t0_us + seq * 5000, 1_000_000 + seq * 5000,
                          seq * 5000, 0xCBD36978, seq & 0xFFF, rssi, -92, 20, 0, 1, 0, 1, 11, 2, 0,
                          32, 384)
        out += frame(cw.T_CSI, hdr + iq.tobytes())
    for _ in range(corrupt):
        i = int(rng.integers(100, len(out)))
        out[i] ^= 0x5A
    path.write_bytes(bytes(out))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--seconds", type=float, default=60)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)
    make(a.out / "RX1.bin", 1, a.seconds, 0.01, rng)
    make(a.out / "RX2.bin", 2, a.seconds, 0.02, rng, gain_step=45, gap=(20, 0.06), corrupt=10)
    (a.out / "SYNTHETIC_DATA.txt").write_text("Synthetic test data from make_synthetic_run.py, not a measurement.\n")
    print(f"wrote synthetic run to {a.out}")


if __name__ == "__main__":
    main()
