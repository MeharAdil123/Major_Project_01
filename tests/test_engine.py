"""Engine v2 on SYNTHETIC data: live = offline, no stale predictions, alarm rule, serial reconnect."""
import time

import numpy as np

from app import engine as E
from app.consistency import SimClock, compare_take
from tests.synthetic.make_synthetic_dataset import make_take
from ml.predict import Predictor
from tests.fake_serial import opener_for
from tests.test_predict import make_models


def synth_take(tmp_path, seconds=12.0):
    meta = dict(session_id="SYNTH_S9_E01_fall", kind="event", activity="fall", position="M", duration_s=seconds,
                cue_s=3.0, subject="S9", instruction="SYNTHETIC")
    folder = tmp_path / "take"
    make_take(folder, meta, np.random.default_rng(3), 1.0)
    return folder


def test_live_equals_offline_on_a_synthetic_take(tmp_path):
    pred = Predictor(make_models(tmp_path / "models"))
    r = compare_take(synth_take(tmp_path), pred)
    assert r["windows"] >= 8
    assert r["max_abs_diff_X"] < 1e-5 and r["max_abs_diff_P"] < 1e-5 and r["max_abs_diff_rssi"] < 1e-4
    assert r["identical"], r


def feed(buf, clock, rx_ids, seconds, seq0=1000):
    raw = np.zeros(384, np.int8)
    raw[1::2] = 20
    for i in range(int(seconds * 200)):
        clock.t = i / 200
        for r in rx_ids:
            buf.push(r, seq0 + i, raw, -40)
    return seq0 + int(seconds * 200)


def test_silent_receiver_never_gives_a_prediction(tmp_path):
    pred = Predictor(make_models(tmp_path / "models"))
    clock = SimClock()
    buf = E.Buffer(clock=clock)
    eng = E.Engine(pred, buf, log_dir=None, clock=clock)
    feed(buf, clock, (1, 2), 6.0)
    assert eng.step()["status"] == "ok"
    # RX2 goes silent (USB unplugged): its old packets stay in the buffer, but no prediction may use them
    raw = np.zeros(384, np.int8)
    for i in range(400):
        clock.t = 6.0 + i / 200
        buf.push(1, 1000 + 1200 + i, raw, -40)
    st = eng.step()
    assert st["status"] == "degraded" and "RX2" in st["reason"] and "fall_prob" not in st
    clock.t += 5.0
    assert eng.step()["status"] == "no_signal"


def test_alarm_k_of_n_with_cooldown(tmp_path):
    pred = Predictor(make_models(tmp_path / "models"))
    clock = SimClock()
    eng = E.Engine(pred, E.Buffer(clock=clock), log_dir=None, clock=clock)
    seq = iter([0.9, 0.1, 0.8, 0.9, 0.9, 0.2, 0.9, 0.9])
    pred.predict = lambda X, r, P: dict(label="stand", confidence=0.9, probs={"stand": 1.0}, motion=0.0,
                                        fall_prob=next(seq), uncertain=False, presence_prob=1.0, state="stand",
                                        state_probs={}, event="none", event_probs={"none": 1.0})
    feed(eng.buf, clock, (1, 2), 6.0)
    alerts = []
    for k in range(8):
        clock.t = 6.0 + 0.5 * k
        eng.buf.arrivals = {r: type(eng.buf.arrivals[r])([(clock.t, 0)], maxlen=600) for r in (1, 2)}
        alerts.append(eng.step()["alert"])
    # theta 0.5, 2-of-3: first alarm at the 3rd window (0.9, 0.1, 0.8), then 10 s cooldown
    assert alerts == [None, None, "FALL", None, None, None, None, None]


def test_serial_source_reconnects_after_port_death():
    buf = E.Buffer()
    opened = []

    def opener(port, baud):
        opened.append(port)
        spec = {"fake2": {"mode": "die", "die_after": 0.3}} if len(opened) == 1 else {}
        return opener_for(spec)(port, baud)

    s = E.SerialSource(buf, 2, port="fake2", opener=opener, retry_s=0.1)
    s.start()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and not (s.reconnects >= 1 and s.connected and len(buf.d[2]) > 50):
        time.sleep(0.05)
    s.stop.set()
    assert s.reconnects >= 1 and len(opened) >= 2 and "SerialException" in (s.last_error or "")
    assert len(buf.d[2]) > 50                                   # packets flow again after the reconnect


def test_every_completed_env_check_is_logged(tmp_path, monkeypatch):
    """Bug 2026-10-23: only the first environment-check result per session reached the live log."""
    import json
    from app import envcheck as ec

    class StubCheck:                                     # done after 2 windows; verdict alternates per run
        runs = 0

        def __init__(self, *a, **k):
            StubCheck.runs += 1
            self.n, self.result, self.verdict = 0, None, "ok" if StubCheck.runs % 2 == 0 else "differs"

        def add(self, t, w, out):
            self.n += 1
            if self.n >= 2:
                self.result = dict(verdict=self.verdict)

        def status(self, t):
            return dict(state="done", **self.result) if self.result else dict(state="running", windows=self.n)

    monkeypatch.setattr(ec, "load_baseline", lambda d: {})
    monkeypatch.setattr(ec, "EnvCheck", StubCheck)
    pred = Predictor(make_models(tmp_path / "models"))
    clock = SimClock()
    eng = E.Engine(pred, E.Buffer(clock=clock), log_dir=tmp_path / "logs", clock=clock)
    feed(eng.buf, clock, (1, 2), 6.0)
    for run in range(3):
        eng.start_env_check(1.0)
        for k in range(4):
            clock.t += 0.5
            eng.buf.arrivals = {r: type(eng.buf.arrivals[r])([(clock.t, 0)], maxlen=600) for r in (1, 2)}
            assert eng.step()["status"] == "ok"
    eng.log.close()
    rows = [json.loads(x) for f in (tmp_path / "logs").glob("live_*.jsonl") for x in f.read_text().splitlines()]
    logged = [r["env"] for r in rows if "env" in r]
    assert [(e["run"], e["verdict"]) for e in logged] == [(1, "differs"), (2, "ok"), (3, "differs")]
