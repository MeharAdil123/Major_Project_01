#!/usr/bin/env python3
"""Read RX1 and RX2 at the same time, show live numbers, and score the E0 bench test.

    python3 rx_check.py                       # find both receivers, run 60 s
    python3 rx_check.py --seconds 120 --save e0_run1
    python3 rx_check.py --only rx1            # one receiver only
    python3 rx_check.py --list                # show serial ports

Receivers are found by their fixed names under /dev/serial/by-id:
  RX1: native USB, name contains its MAC 28:84:85:85:5E:2C
  RX2: UART port (CH343), USB serial 5C38144809, 2 000 000 baud
Override with --rx1 PORT / --rx2 PORT.

Needs only pyserial (ESP-IDF's Python has it:
alias espy=~/.espressif/python_env/idf5.5_py3.12_env/bin/python  ->  espy rx_check.py).
"""
from __future__ import annotations

import argparse
import glob
import json
import struct
import sys
import threading
import time
from pathlib import Path

RX1_DEFAULT = "28:84:85:85:5E:2C"     # matched inside /dev/serial/by-id names
RX2_DEFAULT = "5C38144809"
RX2_BAUD = 2_000_000

SYNC = b"\xA5\x5A"
T_HELLO, T_STATS, T_CSI = 0x01, 0x02, 0x10
HDR = struct.Struct("<BBHIQQIIHbbbBBBBBBBHH")
HDR_FIELDS = ("version", "rx_id", "flags", "seq", "tx_time_us", "rx_time_us", "rx_ctrl_ts",
              "radio_id", "mac_seq", "rssi", "noise_floor", "tx_power_qdbm", "rate",
              "sig_mode", "mcs", "cwb", "channel", "secondary_channel", "reserved",
              "sig_len", "csi_len")
assert HDR.size == 48
F_SEQ_VALID, F_RADIO_MISMATCH = 1, 2

GATE_RATE, GATE_LOSS, GATE_BOTH, GATE_HT40 = 190.0, 0.02, 0.95, 0.95
GATE_CRC_UART = 0.005   # D-011: UART link may lose up to 0.5 % of frames to CRC rejects
GATE_LOSS_UART = 0.03   # D-012: RX2 (UART board) total loss limit


def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


class Decoder:
    def __init__(self):
        self.buf = bytearray()
        self.crc_errors = 0

    def feed(self, data: bytes):
        self.buf += data
        out = []
        while True:
            i = self.buf.find(SYNC)
            if i < 0:
                del self.buf[: max(0, len(self.buf) - 1)]
                return out
            del self.buf[:i]
            if len(self.buf) < 5:
                return out
            ftype, n = struct.unpack_from("<BH", self.buf, 2)
            if n > 2048:
                del self.buf[:1]
                continue
            if len(self.buf) < 7 + n:
                return out
            body = bytes(self.buf[2:5 + n])
            (crc,) = struct.unpack_from("<H", self.buf, 5 + n)
            if crc != crc16(body):
                self.crc_errors += 1
                del self.buf[:1]
                continue
            del self.buf[:7 + n]
            out.append((ftype, body[3:]))


class RxState:
    def __init__(self, name):
        self.name = name
        self.hello = None
        self.stats = []                 # (host_time, dict)
        self.recs = []                  # (host_time, header dict without csi)
        self.dec = Decoder()
        self.bytes = 0
        self.lock = threading.Lock()

    def handle(self, t, ftype, payload):
        with self.lock:
            if ftype == T_HELLO:
                self.hello = json.loads(payload)
            elif ftype == T_STATS:
                self.stats.append((t, json.loads(payload)))
            elif ftype == T_CSI and len(payload) >= HDR.size:
                h = dict(zip(HDR_FIELDS, HDR.unpack_from(payload)))
                if len(payload) == HDR.size + h["csi_len"]:
                    self.recs.append((t, h))


def reader(port, baud, st: RxState, stop: threading.Event, raw_path):
    import serial
    s = serial.Serial()
    s.port, s.baudrate, s.timeout = port, baud, 0.05
    s.dtr = False
    s.rts = False
    try:
        s.open()
    except Exception as e:
        print(f"[{st.name}] cannot open {port}: {e}")
        return
    raw = open(raw_path, "wb") if raw_path else None
    while not stop.is_set():
        chunk = s.read(65536)
        if not chunk:
            continue
        t = time.monotonic()
        st.bytes += len(chunk)
        if raw:
            raw.write(chunk)
        for ftype, payload in st.dec.feed(chunk):
            st.handle(t, ftype, payload)
    s.close()
    if raw:
        raw.close()


def find_port(token):
    for p in sorted(glob.glob("/dev/serial/by-id/*")):
        if token.lower() in p.lower():
            return p
    return None


def summarize(st: RxState, t0, t1):
    """Metrics over records received between host times t0 and t1."""
    recs = [h for t, h in st.recs if t0 <= t <= t1 and h["flags"] & F_SEQ_VALID]
    dur = max(t1 - t0, 1e-9)
    keys = {(h["seq"], h["tx_time_us"]) for h in recs}
    # loss per TX boot segment: a big backwards jump in seq means the TX rebooted
    segs, cur = [], []
    for h in sorted(recs, key=lambda h: h["rx_time_us"]):
        if cur and h["seq"] + 1000 < cur[-1]:
            segs.append(cur)
            cur = []
        cur.append(h["seq"])
    if cur:
        segs.append(cur)
    span = sum(max(s) - min(s) + 1 for s in segs)
    got = sum(len(set(s)) for s in segs)
    cwb = sum(h["cwb"] for h in recs)
    rssi = [h["rssi"] for h in recs]
    return {
        "n": len(recs), "rate": len(keys) / dur,
        "loss": (1 - got / span) if span else None, "span": span,
        "ht40": cwb / len(recs) if recs else None,
        "rssi_mean": sum(rssi) / len(rssi) if rssi else None,
        "rssi_min": min(rssi) if rssi else None, "rssi_max": max(rssi) if rssi else None,
        "csi_len": sorted({h["csi_len"] for h in recs}),
        "sig_mode": sorted({h["sig_mode"] for h in recs}),
        "mismatch": sum(1 for h in recs if h["flags"] & F_RADIO_MISMATCH),
        "tx_power": sorted({h["tx_power_qdbm"] / 4 for h in recs}),
        "segments": len(segs), "keys": keys,
    }


def stat_delta(st: RxState, key, t0, t1):
    s = [d for t, d in st.stats if t0 <= t <= t1]
    return (s[-1][key] - s[0][key]) if len(s) >= 2 else None


def loss_gate(st: RxState):
    """D-012: the UART receiver (RX2) shows ~1 % extra radio-side loss; limit 3 %."""
    return GATE_LOSS_UART if (st.hello or {}).get("link") == "uart" else GATE_LOSS


def crc_check(st: RxState, m):
    """USB links must be clean. UART links may lose < 0.5 % of frames (D-011);
    the CRC rejects damaged frames, so no corrupt data is kept."""
    n = st.dec.crc_errors
    if (st.hello or {}).get("link") == "uart":
        frac = n / max(m["n"] + n, 1)
        return (f"corrupt frames < {GATE_CRC_UART:.1%} (UART)", frac < GATE_CRC_UART,
                f"CRC errors {n} ({frac:.2%}), rejected, counted as loss")
    return ("no corrupt frames on host", n == 0, f"CRC errors {n}")


def fmt(v, f="{:.1f}"):
    return "-" if v is None else f.format(v)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rx1", help="RX1 port (default: by-id name containing %s)" % RX1_DEFAULT)
    ap.add_argument("--rx2", help="RX2 port (default: by-id name containing %s)" % RX2_DEFAULT)
    ap.add_argument("--rx2-baud", type=int, default=RX2_BAUD)
    ap.add_argument("--only", choices=["rx1", "rx2"])
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("--warmup", type=float, default=5)
    ap.add_argument("--save", type=Path, help="folder for raw streams + summary.json")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    if a.list:
        for p in sorted(glob.glob("/dev/serial/by-id/*")):
            print(p)
        return 0

    plan = []
    if a.only != "rx2":
        p = a.rx1 or find_port(RX1_DEFAULT)
        if not p:
            print("RX1 not found (native USB, MAC %s). Check cable/port, or pass --rx1." % RX1_DEFAULT)
            return 1
        plan.append(("RX1", p, 115200))      # baud is ignored by native USB
    if a.only != "rx1":
        p = a.rx2 or find_port(RX2_DEFAULT)
        if not p:
            print("RX2 not found (UART port, serial %s). Check cable/port, or pass --rx2." % RX2_DEFAULT)
            return 1
        plan.append(("RX2", p, a.rx2_baud))

    if a.save:
        a.save.mkdir(parents=True, exist_ok=False)
    states, threads, stop = {}, [], threading.Event()
    for name, port, baud in plan:
        st = RxState(name)
        states[name] = st
        raw = a.save / f"{name}.bin" if a.save else None
        th = threading.Thread(target=reader, args=(port, baud, st, stop, raw), daemon=True)
        th.start()
        threads.append(th)
        print(f"{name}: {port} @ {baud}")

    t_start = time.monotonic()
    t_meas = t_start + a.warmup
    t_end = t_meas + a.seconds
    print(f"warm-up {a.warmup:.0f} s, then measuring {a.seconds:.0f} s. Ctrl+C stops early.\n")
    hdr = f"{'t':>5} " + " ".join(f"| {n}: pkt/s  HT40  RSSI  len  loss" for n in states)
    print(hdr)
    try:
        while time.monotonic() < t_end:
            time.sleep(1.0)
            now = time.monotonic()
            cols = []
            for n, st in states.items():
                with st.lock:
                    m = summarize(st, now - 1.0, now)
                cols.append(f"| {n}: {fmt(m['rate'], '{:5.0f}')}  {fmt(m['ht40'] and m['ht40']*100, '{:3.0f}%')}"
                            f"  {fmt(m['rssi_mean'], '{:4.0f}')}  {(m['csi_len'] or ['-'])[0]!s:>3}"
                            f"  {fmt(m['loss'] and m['loss']*100, '{:4.1f}%')}")
            phase = "warm" if now < t_meas else ""
            print(f"{now - t_start:5.0f} " + " ".join(cols) + f" {phase}", flush=True)
    except KeyboardInterrupt:
        t_end = time.monotonic()
    stop.set()
    for th in threads:
        th.join(timeout=2)

    # ---------------- E0 summary over the measurement window
    print("\n================ E0 summary ================")
    fails = 0
    res = {}
    for n, st in states.items():
        m = summarize(st, t_meas, t_end)
        res[n] = m
        h = st.hello or {}
        print(f"\n{n}: MAC {h.get('mac','?')}  link {h.get('link','?')}  fw {h.get('fw','?')} "
              f"{h.get('app_version','')}  bw_cfg {h.get('bw_cfg','?')}  radio_ok {h.get('radio_ok','?')}")
        checks = [
            ("receives HELLO", st.hello is not None, ""),
            (f"rate >= {GATE_RATE:.0f}/s", m["rate"] >= GATE_RATE, f"{m['rate']:.1f}/s"),
            (f"loss < {loss_gate(st):.0%}", m["loss"] is not None and m["loss"] < loss_gate(st),
             f"{fmt(m['loss'] and m['loss']*100, '{:.2f}%')} of {m['span']} (TX boots seen: {m['segments']})"),
            (f"HT40 >= {GATE_HT40:.0%}", m["ht40"] is not None and m["ht40"] >= GATE_HT40,
             f"40 MHz in {fmt(m['ht40'] and m['ht40']*100, '{:.1f}%')}; sig_mode {m['sig_mode']}; CSI length {m['csi_len']}"),
            ("TX settings match", m["mismatch"] == 0, f"{m['mismatch']} frames with another radio_id"),
            ("no drops on board/link", (stat_delta(st, 'q_drop', t_meas, t_end) or 0) == 0
             and (stat_delta(st, 'link_drop', t_meas, t_end) or 0) == 0,
             f"queue +{stat_delta(st, 'q_drop', t_meas, t_end)}, link +{stat_delta(st, 'link_drop', t_meas, t_end)}"),
            crc_check(st, m),
        ]
        for name, ok, detail in checks:
            fails += not ok
            print(f"  [{'PASS' if ok else 'FAIL'}] {name:24s} {detail}")
        acc = stat_delta(st, "accepted", t_meas, t_end)
        got = sum(1 for t, h in st.recs if t_meas <= t <= t_end)
        if acc:
            # board-side counter vs host-side records over (almost) the same window
            print(f"  [info] link delivery: board accepted {acc}, host got {got} "
                  f"({100 * got / acc:.1f}%) -> radio-side loss ~{fmt(m['loss'] and max(m['loss'] - max(0, 1 - got / acc), 0) * 100, '{:.2f}%')}, "
                  f"link-side loss ~{max(0, 100 * (1 - got / acc)):.2f}%")
        print(f"  [info] RSSI {fmt(m['rssi_mean'])} dBm (min {m['rssi_min']}, max {m['rssi_max']}); "
              f"TX power seen {m['tx_power']} dBm")
    if len(res) == 2:
        k1, k2 = res["RX1"]["keys"], res["RX2"]["keys"]
        union = k1 | k2
        both = len(k1 & k2) / len(union) if union else 0
        ok = both >= GATE_BOTH
        fails += not ok
        print(f"\n  [{'PASS' if ok else 'FAIL'}] seen by both >= {GATE_BOTH:.0%}   {both*100:.1f}% of {len(union)} packets")
    print(f"\nE0: {'PASS' if fails == 0 else f'FAIL ({fails} check(s))'}")

    if a.save:
        out = {n: {k: v for k, v in m.items() if k != "keys"} for n, m in res.items()}
        for n, st in states.items():
            out[n]["hello"] = st.hello
        (a.save / "summary.json").write_text(json.dumps(out, indent=2))
        print(f"saved raw streams and summary.json in {a.save}")
    return 0 if fails == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
