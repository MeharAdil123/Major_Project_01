#!/usr/bin/env python3
"""Live inference engine: serial (or replay) -> preprocessing -> Predictor -> room state.

    python3 -m app.engine --serial                                  # live boards
    python3 -m app.engine --replay data/raw/<session> [more ...] --loop
    python3 -m app.engine --replay-dir data_synth/raw --pattern "*P1_T*" --models models_synth

Every 0.5 s it takes the latest 2 s of packets seen by both receivers, builds the same window
as training (pipeline/preprocess.py), asks the Predictor and publishes a state dict:

  {"t": 12.5, "status": "ok|degraded|no_signal", "label": "sit", "label_smoothed": "sit",
   "confidence": 0.81, "uncertain": false, "probs": {...}, "motion": 0.012, "fall_prob": 0.02,
   "alert": null | "FALL", "rx": {"RX1": {"rate": 198, "rssi": -45, "age_s": 0.01}, ...},
   "window_missing": [0.01, 0.02], "synthetic_model": false}

The UI (app/live_app.py) reads engine.latest / engine.history. Only predictions are logged
(logs/), never raw CSI.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
import threading
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from host import csiwire as cw  # noqa: E402
from pipeline import preprocess as pp  # noqa: E402

RX1_TOKEN, RX2_TOKEN = "28:84:85:85:5E:2C", "5C38144809"
BAUD = {1: 115200, 2: 2_000_000}
STEP_S = 0.5
SKEW_PKTS = 10                  # wait this many packets for the slower receiver
SMOOTH_N = 3                    # majority vote over the last 3 windows (1.5 s)
FALL_P = 0.6
FALL_COOLDOWN_S = 10.0


class Buffer:
    """Recent packets per receiver: seq -> (csi_raw, rssi)."""

    def __init__(self, keep_pkts=800):
        self.keep = keep_pkts
        self.d = {r: collections.OrderedDict() for r in pp.RX_IDS}
        self.arrivals = {r: collections.deque(maxlen=400) for r in pp.RX_IDS}
        self.last_rssi = {r: None for r in pp.RX_IDS}
        self.lock = threading.Lock()

    def push(self, rx, seq, csi_raw, rssi):
        with self.lock:
            q = self.d[rx]
            if q and abs(seq - next(reversed(q))) > 2000:     # TX rebooted or new replay take
                q.clear()
            q[seq] = (csi_raw, rssi)
            while len(q) > self.keep:
                q.popitem(last=False)
            self.arrivals[rx].append(time.monotonic())
            self.last_rssi[rx] = rssi

    def snapshot(self):
        with self.lock:
            return {r: list(q.items()) for r, q in self.d.items()}

    def health(self):
        now = time.monotonic()
        out = {}
        with self.lock:
            for r in pp.RX_IDS:
                a = self.arrivals[r]
                rate = sum(1 for t in a if now - t <= 1.0)
                out[f"RX{r}"] = dict(rate=rate, rssi=self.last_rssi[r],
                                     age_s=round(now - a[-1], 2) if a else None)
        return out


class SerialSource(threading.Thread):
    def __init__(self, buf: Buffer, rx: int, port: str):
        super().__init__(daemon=True)
        import serial
        self.buf, self.rx = buf, rx
        self.s = serial.Serial()
        self.s.port, self.s.baudrate, self.s.timeout = port, BAUD[rx], 0.05
        self.s.dtr = False
        self.s.rts = False
        self.s.open()
        self.dec = cw.StreamDecoder()
        self.stop = threading.Event()

    def run(self):
        while not self.stop.is_set():
            chunk = self.s.read(65536)
            if not chunk:
                continue
            for ftype, payload in self.dec.feed(chunk):
                if ftype != cw.T_CSI:
                    continue
                r = cw.parse_csi(payload)
                if r is None:
                    continue
                h, csi = r
                fl = int(h["flags"])
                if not (fl & cw.F_SEQ_VALID) or (fl & cw.F_RADIO_MISMATCH):
                    continue
                self.buf.push(self.rx, int(h["seq"]), csi, float(h["rssi"]))


class ReplaySource(threading.Thread):
    """Plays saved takes at real speed, one after another (seq renumbered to be continuous)."""

    def __init__(self, buf: Buffer, folders, loop=False, speed=1.0):
        super().__init__(daemon=True)
        self.buf, self.folders, self.loop, self.speed = buf, list(folders), loop, speed
        self.current = None
        self.stop = threading.Event()

    def run(self):
        offset = 0
        while not self.stop.is_set():
            for folder in self.folders:
                if self.stop.is_set():
                    return
                recs = {}
                for r in pp.RX_IDS:
                    f = Path(folder) / f"RX{r}.bin"
                    if f.exists():
                        rec = cw.load(f)
                        ok = (rec.hdr["flags"] & cw.F_SEQ_VALID) != 0
                        recs[r] = (rec.hdr[ok], rec.csi_raw[ok])
                if not recs:
                    continue
                meta_f = Path(folder) / "meta.json"
                self.current = json.loads(meta_f.read_text()) if meta_f.exists() else {"session_id": str(folder)}
                seq0 = min(int(h["seq"][0]) for h, _ in recs.values())
                events = sorted((int(h["seq"][i]) - seq0, r, i) for r, (h, _) in recs.items() for i in range(len(h)))
                t0 = time.monotonic()
                for rel, r, i in events:
                    if self.stop.is_set():
                        return
                    due = t0 + rel / pp.FS_IN / self.speed
                    dt = due - time.monotonic()
                    if dt > 0:
                        time.sleep(dt)
                    h, csi = recs[r]
                    self.buf.push(r, offset + rel, csi[i], float(h["rssi"][i]))
                offset += events[-1][0] + 1 if events else 0
            if not self.loop:
                return


class Engine:
    def __init__(self, predictor, buf: Buffer, log_dir: Path | None = ROOT / "logs"):
        self.pred, self.buf = predictor, buf
        self.latest = dict(status="starting")
        self.history = collections.deque(maxlen=2000)
        self.votes = collections.deque(maxlen=SMOOTH_N)
        self.fall_votes = collections.deque(maxlen=3)
        self.last_alert_t = -1e9
        self.stop = threading.Event()
        self.t0 = time.monotonic()
        self.source_info = None
        self.log = None
        if log_dir:
            log_dir.mkdir(parents=True, exist_ok=True)
            self.log = open(log_dir / time.strftime("live_%Y%m%d_%H%M%S.jsonl"), "a")

    def step(self):
        t = round(time.monotonic() - self.t0, 2)
        health = self.buf.health()
        snap = self.buf.snapshot()
        state = dict(t=t, rx=health, alert=None, synthetic_model=self.pred.synthetic,
                     source=self.source_info() if callable(self.source_info) else None)
        if any(len(snap[r]) < pp.WIN * pp.DECIM for r in pp.RX_IDS):
            state.update(status="no_signal", label="unknown", label_smoothed="unknown", confidence=0.0,
                         uncertain=True, reason="waiting for 2 s of packets from both receivers")
            return self._publish(state)
        hi = min(snap[r][-1][0] for r in pp.RX_IDS) - SKEW_PKTS
        lo = hi - pp.WIN * pp.DECIM + 1
        per_rx = {}
        for r in pp.RX_IDS:
            items = [(s, v) for s, v in snap[r] if lo <= s <= hi]
            if not items:
                continue
            seq = np.array([s for s, _ in items])
            raw = np.stack([v[0] for _, v in items])
            rssi = np.array([v[1] for _, v in items])
            per_rx[r] = pp.records_from_arrays(seq, raw, rssi)
        try:
            grid = pp.build_grid(per_rx, lo, hi)
            w = pp.cut_windows(grid, [0])
        except ValueError as e:
            state.update(status="degraded", label="unknown", label_smoothed="unknown", confidence=0.0,
                         uncertain=True, reason=str(e))
            return self._publish(state)
        state["window_missing"] = [round(float(x), 3) for x in w["miss_frac"][0]]
        if len(w["ok"]) == 0 or not w["ok"][0]:
            state.update(status="degraded", label="unknown", label_smoothed="unknown", confidence=0.0,
                         uncertain=True, reason="too many missing packets in the last 2 s")
            return self._publish(state)
        out = self.pred.predict(w["X"][0], w["rssi"][0])
        state.update(status="ok", **out)
        self.votes.append(out["label"] if not out["uncertain"] else "uncertain")
        vals, cnt = np.unique(list(self.votes), return_counts=True)
        state["label_smoothed"] = str(vals[np.argmax(cnt)])
        self.fall_votes.append(out["fall_prob"] >= FALL_P)
        if sum(self.fall_votes) >= 2 and t - self.last_alert_t > FALL_COOLDOWN_S:
            state["alert"] = "FALL"
            self.last_alert_t = t
        return self._publish(state)

    def _publish(self, state):
        self.latest = state
        self.history.append(state)
        if self.log:
            keep = {k: state.get(k) for k in ("t", "status", "label", "label_smoothed", "confidence",
                                              "fall_prob", "alert", "motion")}
            self.log.write(json.dumps(keep) + "\n")
            self.log.flush()
        return state

    def run(self):
        while not self.stop.is_set():
            t_next = time.monotonic() + STEP_S
            try:
                self.step()
            except Exception as e:  # keep the demo alive; show the error in the UI
                self.latest = dict(status="error", reason=repr(e), label="unknown")
            time.sleep(max(0.0, t_next - time.monotonic()))


def find_port(token):
    d = Path("/dev/serial/by-id")
    if d.exists():
        for p in sorted(d.iterdir()):
            if token in p.name:
                return str(p)
    return None


def build(args):
    """Create buffer, sources and engine from CLI-style args (also used by the Streamlit app)."""
    from ml.predict import Predictor
    pred = Predictor(args.models)
    buf = Buffer()
    sources = []
    if args.serial:
        for rx, tok, override in ((1, RX1_TOKEN, args.rx1), (2, RX2_TOKEN, args.rx2)):
            port = override or find_port(tok)
            if not port:
                raise SystemExit(f"RX{rx} port not found")
            sources.append(SerialSource(buf, rx, port))
    else:
        folders = list(args.replay or [])
        if args.replay_dir:
            folders += sorted(str(p.parent) for p in Path(args.replay_dir).glob(f"{args.pattern}/meta.json"))
        if not folders:
            raise SystemExit("nothing to replay")
        sources.append(ReplaySource(buf, folders, loop=args.loop, speed=args.speed))
    eng = Engine(pred, buf)
    rs = [s for s in sources if isinstance(s, ReplaySource)]
    if rs:
        eng.source_info = lambda: (rs[0].current or {}).get("session_id")
    for s in sources:
        s.start()
    threading.Thread(target=eng.run, daemon=True).start()
    return eng, sources


def parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", default=str(ROOT / "models"))
    ap.add_argument("--serial", action="store_true")
    ap.add_argument("--rx1")
    ap.add_argument("--rx2")
    ap.add_argument("--replay", nargs="*")
    ap.add_argument("--replay-dir")
    ap.add_argument("--pattern", default="*")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--seconds", type=float, default=0, help="stop after N s (0 = run until Ctrl+C)")
    return ap


def main():
    args = parser().parse_args()
    eng, _ = build(args)
    t_end = time.monotonic() + args.seconds if args.seconds else None
    try:
        while t_end is None or time.monotonic() < t_end:
            time.sleep(STEP_S)
            s = eng.latest
            rx = " ".join(f"{k}:{v['rate']}/s" for k, v in s.get("rx", {}).items())
            print(f"t={s.get('t')} {s.get('status'):<9} {s.get('label_smoothed', '-'):<10} "
                  f"conf={s.get('confidence', 0):.2f} fall={s.get('fall_prob', 0):.2f} "
                  f"{'ALERT ' + s['alert'] if s.get('alert') else ''} [{rx}] src={s.get('source')}", flush=True)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
