"""Run app.engine in its own process for the dashboard (Phase 5 live test, D-057).

In one process, Streamlit's page reruns held the interpreter lock and the engine fell behind: live steps came
every ~1.7 s instead of 0.5 s, while the same engine alone stepped every 0.50 s (step 243 ms median;
results/phase5/live_library/TEST_CONDITIONS.md). Here the engine (serial readers, windows, models, logging)
runs in a child process; the dashboard gets state / events / environment check / heatmaps through a queue
and sends commands (marker, start environment check) back. The engine code itself is unchanged.
"""
from __future__ import annotations

import collections
import json
import os
import queue
import secrets
import socket
import subprocess
import sys
import threading
import time
from multiprocessing.connection import Client, Listener
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUSH_S = 0.5          # child -> parent state rate
HEAT_S = 2.0          # child -> parent heatmap rate


def serve(port: int, authkey: bytes, argv):
    """Child program: run the engine and stream its state to the one dashboard that connects."""
    sys.path.insert(0, str(ROOT))
    from app import engine as E
    args = E.parser().parse_args(list(argv))
    eng, _ = E.build(args)
    with Listener(("127.0.0.1", port), authkey=authkey) as lst, lst.accept() as conn:
        last_t, last_heat, n_events = None, 0.0, 0
        try:
            while True:
                while conn.poll(0):
                    cmd, arg = conn.recv()
                    if cmd == "mark":
                        conn.send(("mark", eng.mark(arg)))
                    elif cmd == "env":
                        eng.start_env_check(arg)
                s = eng.latest
                if s.get("t") != last_t:
                    last_t = s.get("t")
                    conn.send(("state", s))
                if len(eng.events) != n_events:
                    n_events = len(eng.events)
                    conn.send(("events", list(eng.events)))
                conn.send(("env", eng.env))
                if time.monotonic() - last_heat > HEAT_S:
                    last_heat = time.monotonic()
                    h = eng.heatmap(6.0)
                    if h is not None:
                        conn.send(("heat", h))
                time.sleep(PUSH_S / 2)
        except (EOFError, BrokenPipeError, ConnectionResetError, OSError):
            pass                                            # dashboard went away: stop the engine
    os._exit(0)


class _PredInfo:
    """What the dashboard needs from the Predictor, read from model_meta.json (no models loaded here)."""

    def __init__(self, models_dir):
        d = Path(models_dir)
        self.meta = {t: json.loads((d / t / "model_meta.json").read_text())
                     for t in ("presence", "state", "events", "fall_alarm") if (d / t / "model_meta.json").exists()}
        self.window_s = float(self.meta["events"]["window_s"])
        a = self.meta["fall_alarm"]["alarm"] if "fall_alarm" in self.meta else self.meta["events"]["alarm"]
        self.alarm = dict(theta=a["theta"], k=a["k"], n=a["n"], cooldown_s=a["cooldown_s"])
        self.synthetic = any(bool(m.get("synthetic")) for m in self.meta.values())


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class EngineProxy:
    """Same attributes the dashboard uses on app.engine.Engine: latest, history, events, env, pred,
    heatmap(), mark(), start_env_check(). The engine runs as `python -m app.engine_proc` (own process)."""

    def __init__(self, argv, models_dir):
        port, key = _free_port(), secrets.token_bytes(16)
        env = dict(os.environ, CSI_ENGINE_KEY=key.hex())
        self.proc = subprocess.Popen([sys.executable, "-m", "app.engine_proc", str(port), "--", *argv], cwd=ROOT, env=env)
        self.pred = _PredInfo(models_dir)
        self.latest = dict(status="starting", reason="engine process starting")
        self.history = collections.deque(maxlen=4000)
        self.events = collections.deque(maxlen=200)
        self.env, self._heat, self.conn = None, None, None
        self._lock = threading.Lock()
        threading.Thread(target=self._run, args=(port, key), daemon=True).start()

    def _run(self, port, key):
        for _ in range(120):                                # engine start (models, ports) takes a few seconds
            try:
                self.conn = Client(("127.0.0.1", port), authkey=key)
                break
            except (ConnectionRefusedError, OSError):
                if self.proc.poll() is not None:
                    self.latest = dict(status="error", reason=f"engine process exited ({self.proc.returncode})")
                    return
                time.sleep(0.5)
        while True:
            try:
                kind, val = self.conn.recv()
            except (EOFError, OSError):
                self.latest = dict(status="error", reason="engine process stopped")
                return
            if kind == "state":
                self.latest = val
                self.history.append(val)
            elif kind == "events":
                self.events = collections.deque(val, maxlen=200)
            elif kind == "env":
                self.env = val
            elif kind == "heat":
                self._heat = val

    def heatmap(self, seconds=6.0):
        return self._heat

    def _send(self, msg):
        if self.conn is not None:
            with self._lock:
                self.conn.send(msg)

    def mark(self, label):
        self._send(("mark", label))
        return dict(t=float(self.latest.get("t") or 0.0), wall=time.strftime("%H:%M:%S"))

    def start_env_check(self, seconds=60):
        self._send(("env", seconds))


if __name__ == "__main__":
    port = int(sys.argv[1])
    rest = sys.argv[sys.argv.index("--") + 1:]
    serve(port, bytes.fromhex(os.environ["CSI_ENGINE_KEY"]), rest)
