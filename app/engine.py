#!/usr/bin/env python3
"""Live inference engine v2: serial (or replay) -> preprocess v2 -> features f2 -> Predictor p2 -> room state.

    python3 -m app.engine --replay data/raw/<session> [more ...] [--loop] [--speed 1]
    python3 -m app.engine --replay-dir data/raw --pattern "*S6_E2*" --seconds 60
    python3 -m app.engine --serial                       # live boards (laptop Wi-Fi + Bluetooth off, D-032)

Every STEP_S (0.5 s) the engine takes the newest packets seen by both receivers, builds the same 4 s window
as training (pipeline/preprocess.window with its 0.25 s margins, so the window equals the offline one) and
asks the Predictor. Published state (engine.latest; history in engine.history):

  {"t", "status": "ok|degraded|no_signal|starting|error", "reason", "label", "label_smoothed", "confidence",
   "uncertain", "probs", "presence_prob", "state", "event", "event_probs", "motion", "fall_prob",
   "alert": None | "FALL", "rx": {"RX1": {"rate", "rssi", "age_s", "loss_pct", "connected", "reconnects"}, ...},
   "window_seq0", "window_missing", "source", "truth", "env"}

A receiver silent for more than NO_SIGNAL_S never yields a prediction on old packets (audit E1): one silent RX
-> "degraded", both -> "no_signal". Serial ports reconnect by their /dev/serial/by-id name. Only predictions
and health are logged (logs/live_*.jsonl), never raw CSI.
"""
from __future__ import annotations

import os

# One BLAS thread: the per-window SVDs are small (400 x 114); multi-threaded BLAS on this 2-core laptop
# made engine steps 2x slower and very uneven when the dashboard ran alongside (results/phase5/step_timing.log).
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

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
from pipeline import labels as lb  # noqa: E402
from pipeline import preprocess as pp  # noqa: E402

RX1_TOKEN, RX2_TOKEN = "28:84:85:85:5E:2C", "5C38144809"
TOKENS = {1: RX1_TOKEN, 2: RX2_TOKEN}
BAUD = {1: 115200, 2: 2_000_000}
STEP_S = 0.5
SKEW_PKTS = 10                  # wait this many packets for the slower receiver
NO_SIGNAL_S = 1.0               # a receiver silent longer than this gives no prediction
STALL_S = 2.5                   # serial: no bytes this long -> reconnect
SMOOTH_N = 3                    # majority over the last 3 windows
KEEP_PKTS = 2000                # 10 s of packets per receiver (window + margins + heatmaps)


class Buffer:
    """Recent packets per receiver: seq -> (csi_raw int8[384], rssi). Times come from `clock`."""

    def __init__(self, clock=time.monotonic, keep=KEEP_PKTS):
        self.clock, self.keep = clock, keep
        self.d = {r: collections.OrderedDict() for r in pp.RX_IDS}
        self.arrivals = {r: collections.deque(maxlen=600) for r in pp.RX_IDS}
        self.last_rssi = {r: None for r in pp.RX_IDS}
        self.lock = threading.Lock()

    def push(self, rx, seq, csi_raw, rssi):
        with self.lock:
            q = self.d[rx]
            if q and abs(seq - next(reversed(q))) > 2000:     # TX rebooted or a new replay take
                q.clear()
            q[seq] = (np.asarray(csi_raw, np.int8), float(rssi))
            while len(q) > self.keep:
                q.popitem(last=False)
            self.arrivals[rx].append((self.clock(), seq))
            self.last_rssi[rx] = float(rssi)

    def snapshot(self):
        with self.lock:
            return {r: list(q.items()) for r, q in self.d.items()}

    def health(self):
        now = self.clock()
        out = {}
        with self.lock:
            for r in pp.RX_IDS:
                a = self.arrivals[r]
                recent = [s for t, s in a if now - t <= 2.0]
                loss = (1 - len(recent) / (max(recent) - min(recent) + 1)) * 100 if len(recent) > 20 else None
                out[f"RX{r}"] = dict(rate=sum(1 for t, _ in a if now - t <= 1.0), rssi=self.last_rssi[r],
                                     age_s=round(now - a[-1][0], 2) if a else None,
                                     loss_pct=round(loss, 1) if loss is not None else None)
        return out


def find_port(token):
    d = Path("/dev/serial/by-id")
    if d.exists():
        for p in sorted(d.iterdir()):
            if token in p.name:
                return str(p)
    return None


def open_serial(port, baud):
    import serial
    s = serial.Serial()
    s.port, s.baudrate, s.timeout = port, baud, 0.05
    s.dtr = False
    s.rts = False
    s.open()
    return s


class SerialSource(threading.Thread):
    """One receiver. Reconnects by its by-id token after an error or STALL_S without bytes."""

    def __init__(self, buf: Buffer, rx: int, port: str | None = None, opener=open_serial, find=find_port, retry_s=2.0):
        super().__init__(daemon=True)
        self.buf, self.rx, self.port_override = buf, rx, port
        self.opener, self.find, self.retry_s = opener, find, retry_s
        self.connected, self.reconnects, self.last_error, self.bytes = False, 0, None, 0
        self.stop = threading.Event()

    def run(self):
        first = True
        while not self.stop.is_set():
            port = self.port_override or self.find(TOKENS[self.rx])
            if not port:
                self.last_error = f"RX{self.rx}: port not found"
                self.stop.wait(self.retry_s)
                continue
            try:
                s = self.opener(port, BAUD[self.rx])
            except Exception as e:  # noqa: BLE001  any open error -> retry
                self.last_error = f"open {port}: {e}"
                self.stop.wait(self.retry_s)
                continue
            if not first:
                self.reconnects += 1
            first = False
            self.connected, dec, last = True, cw.StreamDecoder(), time.monotonic()
            try:
                while not self.stop.is_set():
                    chunk = s.read(65536)
                    if not chunk:
                        if time.monotonic() - last > STALL_S:
                            raise IOError(f"no bytes for {STALL_S} s")
                        continue
                    last = time.monotonic()
                    self.bytes += len(chunk)
                    for ftype, payload in dec.feed(chunk):
                        if ftype != cw.T_CSI:
                            continue
                        r = cw.parse_csi(payload)
                        if r is None:
                            continue
                        h, csi = r
                        fl = int(h["flags"])
                        if (fl & cw.F_SEQ_VALID) and not (fl & cw.F_RADIO_MISMATCH):
                            self.buf.push(self.rx, int(h["seq"]), csi, float(h["rssi"]))
            except Exception as e:  # noqa: BLE001  port died -> reconnect
                self.last_error = f"{type(e).__name__}: {e}"
            finally:
                self.connected = False
                try:
                    s.close()
                except Exception:  # noqa: BLE001
                    pass
            self.stop.wait(self.retry_s)


def take_packets(folder: Path):
    """All packets of a recorded take: list of (seq, rx, csi_raw, rssi) sorted by seq (ours, longest TX segment)."""
    ev = []
    for r in pp.RX_IDS:
        f = Path(folder) / f"RX{r}.bin"
        if not f.exists():
            continue
        rec = cw.load(f)
        h = rec.hdr
        ok = ((h["flags"] & cw.F_SEQ_VALID) != 0) & ((h["flags"] & cw.F_RADIO_MISMATCH) == 0)
        h, raw = h[ok], rec.csi_raw[ok]
        if len(h):
            seg = max(cw.tx_segments(h["seq"]), key=lambda s: s.stop - s.start)
            h, raw = h[seg], raw[seg]
        ev += [(int(h["seq"][i]), r, raw[i], float(h["rssi"][i])) for i in range(len(h))]
    ev.sort(key=lambda e: (e[0], e[1]))
    return ev


def truth_at(meta: dict, onset: dict | None, t: float) -> str:
    """True label at take time t (s): the activity for state takes; for event takes the event inside the
    detected action interval, the start posture before it and the end posture after it."""
    if meta.get("kind") != "event":
        return meta.get("activity", "?")
    act = meta["activity"]
    pre = "walk" if lb.starts_walking(meta) else lb.PRE_STATE[act]
    if onset and onset.get("detected"):
        if t < onset["onset_s"]:
            return pre
        if t <= onset["end_s"]:
            return act
        return lb.POST_STATE[act]
    return pre if t < (meta.get("cue_s") or 0) else f"{act}?"


class ReplaySource(threading.Thread):
    """Plays recorded takes at real speed (x speed), one after another, with the true label available."""

    def __init__(self, buf: Buffer, folders, loop=False, speed=1.0, clock=time.monotonic, sleep=time.sleep):
        super().__init__(daemon=True)
        self.buf, self.folders, self.loop, self.speed = buf, [Path(f) for f in folders], loop, speed
        self.clock, self.sleep = clock, sleep
        self.current, self.onset, self.take_t0, self.seq_first = None, None, None, None
        self.stop = threading.Event()
        self.onsets = _load_onsets()

    def info(self):
        if not self.current:
            return None, None
        t = (self.clock() - self.take_t0) * self.speed
        return self.current["session_id"], truth_at(self.current, self.onset, t)

    def run(self):
        offset = 0
        while not self.stop.is_set():
            for folder in self.folders:
                if self.stop.is_set():
                    return
                ev = take_packets(folder)
                if not ev:
                    continue
                meta_f = folder / "meta.json"
                self.current = json.loads(meta_f.read_text()) if meta_f.exists() else {"session_id": folder.name}
                self.onset = self.onsets.get(self.current["session_id"])
                seq0 = ev[0][0]
                self.take_t0 = self.clock()
                for seq, r, raw, rssi in ev:
                    if self.stop.is_set():
                        return
                    due = self.take_t0 + (seq - seq0) / pp.FS_IN / self.speed
                    dt = due - self.clock()
                    if dt > 0:
                        self.sleep(dt)
                    self.buf.push(r, offset + seq - seq0, raw, rssi)
                offset += ev[-1][0] - seq0 + 2000 + 1          # next take: the buffer sees a jump and clears
            if not self.loop:
                return


def _load_onsets():
    f = ROOT / "data" / "processed" / "onsets.csv"
    if not f.exists():
        return {}
    import csv
    out = {}
    with open(f, newline="") as fh:
        for r in csv.DictReader(fh):
            out[r["session_id"]] = dict(detected=r["detected"] == "True", onset_s=float(r["onset_s"]),
                                        end_s=float(r["end_s"]))
    return out


class Engine:
    def __init__(self, predictor, buf: Buffer, log_dir: Path | None = ROOT / "logs", clock=None):
        self.pred, self.buf = predictor, buf
        self.clock = clock or buf.clock
        self.win_s = predictor.window_s
        self.span = int(round(self.win_s * pp.FS_IN))
        self.latest = dict(status="starting")
        self.history = collections.deque(maxlen=4000)
        self.events = collections.deque(maxlen=200)          # alarm / event history for the UI
        self.votes = collections.deque(maxlen=SMOOTH_N)
        a = predictor.alarm
        self.alarm_k, self.alarm_theta, self.cooldown = int(a["k"]), float(a["theta"]), float(a["cooldown_s"])
        self.fall_votes = collections.deque(maxlen=int(a["n"]))
        self.last_alert_t = -1e9
        self.stop = threading.Event()
        self.t0 = self.clock()
        self.source_info = None
        self.sources = []
        self.env = None
        self.envcheck = None
        self.models_dir = getattr(predictor, "dir", None)
        self.last_window = None
        self.log = None
        if log_dir:
            log_dir.mkdir(parents=True, exist_ok=True)
            self.log = open(Path(log_dir) / time.strftime("live_%Y%m%d_%H%M%S.jsonl"), "a")

    def start_env_check(self, seconds: float | None = None):
        """Begin the start-up environment check: the room must be EMPTY for `seconds` (default 60)."""
        from app import envcheck as ec
        base = ec.load_baseline(self.models_dir) if self.models_dir else None
        if base is None:
            self.env = dict(state="unavailable", reason="no models/env_baseline.json (run python3 -m ml.train_final)")
            return
        self.envcheck = ec.EnvCheck(base, self.alarm_theta, seconds or ec.CHECK_S, t_start=self.clock() - self.t0)
        self.env = self.envcheck.status(self.clock() - self.t0)

    # ---- the window the live engine sees (also used by the consistency check)
    def current_window(self, snap=None):
        snap = snap or self.buf.snapshot()
        need = self.span + 2 * pp.MARGIN_PKTS
        if any(len(snap[r]) < need for r in pp.RX_IDS):
            return None, f"waiting for {self.win_s + 0.5:g} s of packets from both receivers"
        hi = min(snap[r][-1][0] for r in pp.RX_IDS) - SKEW_PKTS
        lo = hi - need + 1
        per_rx = {}
        for r in pp.RX_IDS:
            items = [(s, v) for s, v in snap[r] if lo <= s <= hi]
            if not items:
                continue
            per_rx[r] = pp.records_from_arrays(np.array([s for s, _ in items]), np.stack([v[0] for _, v in items]),
                                               np.array([v[1] for _, v in items]))
        try:
            grid = pp.build_grid(per_rx, lo, hi)
        except ValueError as e:
            return None, str(e)
        w = pp.window(grid, pp.MARGIN_PKTS, self.win_s)
        w["seq0"] = lo + pp.MARGIN_PKTS
        w["ok"] = bool((w["miss_frac"] <= pp.MAX_MISS_FRAC).all() and (w["max_gap"] <= pp.MAX_GAP_PKTS).all())
        return w, None

    def step(self):
        self._step_t0 = time.perf_counter()
        t = round(self.clock() - self.t0, 2)
        health = self.buf.health()
        for s in self.sources:
            if isinstance(s, SerialSource):
                health[f"RX{s.rx}"].update(connected=s.connected, reconnects=s.reconnects, last_error=s.last_error)
        src, truth = self.source_info() if callable(self.source_info) else (None, None)
        state = dict(t=t, rx=health, alert=None, synthetic_model=self.pred.synthetic, source=src, truth=truth,
                     env=self.env)
        silent = [k for k, v in health.items() if v["age_s"] is None or v["age_s"] > NO_SIGNAL_S]
        if len(silent) == len(pp.RX_IDS):
            return self._publish(dict(state, status="no_signal", label="unknown", label_smoothed="unknown",
                                      confidence=0.0, uncertain=True, reason="no packets from either receiver"))
        if silent:
            return self._publish(dict(state, status="degraded", label="unknown", label_smoothed="unknown",
                                      confidence=0.0, uncertain=True,
                                      reason=f"{', '.join(silent)}: no packets for > {NO_SIGNAL_S:g} s"))
        w, why = self.current_window()
        if w is None:
            return self._publish(dict(state, status="starting" if "waiting" in why else "degraded", label="unknown",
                                      label_smoothed="unknown", confidence=0.0, uncertain=True, reason=why))
        state["window_missing"] = [round(float(x), 3) for x in w["miss_frac"]]
        state["window_seq0"] = int(w["seq0"])
        if not w["ok"]:
            return self._publish(dict(state, status="degraded", label="unknown", label_smoothed="unknown",
                                      confidence=0.0, uncertain=True, reason="too many missing packets in the window"))
        out = self.pred.predict(w["X"], w["rssi"], w["P"])
        self.last_window = w
        if self.envcheck is not None and self.envcheck.result is None:
            self.envcheck.add(t, w, out)
            self.env = self.envcheck.status(t)
            state["env"] = self.env
        state.update(status="ok", **out)
        self.votes.append(out["label"] if not out["uncertain"] else "uncertain")
        vals, cnt = np.unique(list(self.votes), return_counts=True)
        state["label_smoothed"] = str(vals[np.argmax(cnt)])
        self.fall_votes.append(out["fall_prob"] >= self.alarm_theta)
        if sum(self.fall_votes) >= self.alarm_k and t - self.last_alert_t > self.cooldown:
            state["alert"] = "FALL"
            self.last_alert_t = t
            self.events.append(dict(t=t, kind="FALL", fall_prob=out["fall_prob"], source=src, truth=truth))
        elif out["event"] != "none" and out["event_probs"][out["event"]] >= 0.6:
            if not self.events or self.events[-1]["kind"] != out["event"] or t - self.events[-1]["t"] > 3:
                self.events.append(dict(t=t, kind=out["event"], p=out["event_probs"][out["event"]], source=src, truth=truth))
        return self._publish(state)

    def _publish(self, state):
        self.latest = state
        self.history.append(state)
        if self.log:
            keep = {k: state.get(k) for k in ("t", "status", "reason", "label", "label_smoothed", "confidence",
                                              "presence_prob", "event", "fall_prob", "alert", "source", "truth")}
            keep["wall"] = time.strftime("%H:%M:%S")
            keep["step_ms"] = round((time.perf_counter() - getattr(self, "_step_t0", time.perf_counter())) * 1000)
            if self.env:
                keep["env_state"] = self.env.get("state")
                keep["env_windows"] = self.env.get("windows")
            if state.get("env") and state["env"].get("state") == "done" and not getattr(self, "_env_logged", False):
                keep["env"] = state["env"]
                self._env_logged = True
            keep["rx"] = {k: {kk: v.get(kk) for kk in ("rate", "rssi", "age_s", "loss_pct")} for k, v in state["rx"].items()}
            self.log.write(json.dumps(keep, default=float) + "\n")
            self.log.flush()
        return state

    def mark(self, label: str, note: str = ""):
        """Operator marker for a live test ("now doing X"); logged with engine time and wall-clock time."""
        t = round(self.clock() - self.t0, 2)
        m = dict(t=t, kind="MARK", label=label, note=note, wall=time.strftime("%H:%M:%S"))
        self.events.append(dict(m, source=None, truth=label))
        if self.log:
            self.log.write(json.dumps(dict(marker=m)) + "\n")
            self.log.flush()
        return m

    def heatmap(self, seconds=8.0):
        """Last `seconds` of gain-normalised amplitude and sanitised phase per RX (for the dashboard)."""
        snap = self.buf.snapshot()
        if any(len(snap[r]) < 50 for r in pp.RX_IDS):
            return None
        hi = min(snap[r][-1][0] for r in pp.RX_IDS)
        lo = hi - int(seconds * pp.FS_IN) + 1
        per_rx = {}
        for r in pp.RX_IDS:
            items = [(s, v) for s, v in snap[r] if lo <= s <= hi]
            if len(items) < 2:
                return None
            per_rx[r] = pp.records_from_arrays(np.array([s for s, _ in items]), np.stack([v[0] for _, v in items]),
                                               np.array([v[1] for _, v in items]))
        try:
            g = pp.build_grid(per_rx, lo, hi)
        except ValueError:
            return None
        a = pp.normalise(g["amp"])[:, ::4]                    # 50 Hz for display
        ph = g["phase"][:, ::4]
        ph = np.angle(np.exp(1j * (ph - np.angle(np.exp(1j * ph).mean(axis=1, keepdims=True)))))
        return dict(amp_db=20 * np.log10(np.maximum(a / np.median(a, axis=1, keepdims=True), 1e-3)), phase=ph,
                    seconds=seconds)

    def run(self):
        while not self.stop.is_set():
            t_next = time.monotonic() + STEP_S
            try:
                self.step()
            except Exception as e:  # noqa: BLE001  keep the demo alive; show the error in the UI
                self.latest = dict(status="error", reason=repr(e), label="unknown", rx=self.buf.health())
            time.sleep(max(0.0, t_next - time.monotonic()))


def build(args, start=True):
    """Create buffer, sources and engine from CLI-style args (also used by the dashboard)."""
    from threadpoolctl import threadpool_limits
    threadpool_limits(1)                          # also when numpy was imported before this module
    from ml.predict import Predictor
    pred = Predictor(args.models)
    buf = Buffer()
    sources = []
    if args.serial:
        sources = [SerialSource(buf, 1, args.rx1), SerialSource(buf, 2, args.rx2)]
    else:
        folders = list(args.replay or [])
        if args.replay_dir:
            folders += sorted(str(p.parent) for p in Path(args.replay_dir).glob(f"{args.pattern}/meta.json")
                              if not p.parent.name.startswith("_"))
        if not folders:
            raise SystemExit("nothing to replay")
        sources = [ReplaySource(buf, folders, loop=args.loop, speed=args.speed)]
    eng = Engine(pred, buf, log_dir=None if args.no_log else (Path(args.log_dir) if args.log_dir else ROOT / "logs"))
    eng.sources = sources
    rs = [s for s in sources if isinstance(s, ReplaySource)]
    if rs:
        eng.source_info = rs[0].info
    if args.env_check:
        eng.start_env_check(args.env_check)
    if start:
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
    ap.add_argument("--no-log", action="store_true")
    ap.add_argument("--log-dir", help="folder for live_*.jsonl (default logs/)")
    ap.add_argument("--env-check", type=float, default=0, help="start the empty-room check for N s at launch")
    return ap


def main():
    args = parser().parse_args()
    eng, _ = build(args)
    t_end = time.monotonic() + args.seconds if args.seconds else None
    try:
        while t_end is None or time.monotonic() < t_end:
            time.sleep(STEP_S)
            s = eng.latest
            rx = " ".join(f"{k}:{v.get('rate')}/s" for k, v in s.get("rx", {}).items())
            print(f"t={s.get('t')} {s.get('status'):<9} {s.get('label_smoothed', '-'):<9} conf={s.get('confidence', 0):.2f} "
                  f"event={s.get('event', '-'):<9} fall={s.get('fall_prob', 0):.2f} {'ALERT ' + s['alert'] if s.get('alert') else ''}"
                  f"[{rx}] src={s.get('source')} truth={s.get('truth')}", flush=True)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
