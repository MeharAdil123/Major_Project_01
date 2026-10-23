"""Live vs offline consistency (PROMPT Phase 5.2): the engine, fed a recorded take packet by packet, must see
the same windows and give the same predictions as the offline pipeline on the full take.

    from app.consistency import compare_take
    r = compare_take("data/raw/<session>", Predictor("models"))

The take is pushed through app.engine.Buffer/Engine on a simulated clock (no sleeping), stepping every
STEP_S like the live engine. For each window the engine predicted on, the offline window is cut at the same
TX sequence position from the full-take grid (pipeline/preprocess.build_grid + window) and predicted.
Differences can only come from interpolation at the outer edge of the live buffer when a gap of more than
~30 packets sits there; the window's quality gate (longest gap <= 20 packets) normally rules that out.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from app import engine as E
from host import csiwire as cw
from pipeline import preprocess as pp


class SimClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def compare_take(folder, predictor, step_s: float = E.STEP_S) -> dict:
    folder = Path(folder)
    clock = SimClock()
    buf = E.Buffer(clock=clock)
    eng = E.Engine(predictor, buf, log_dir=None, clock=clock)
    ev = E.take_packets(folder)
    seq_first = ev[0][0]
    step_pkts = int(round(step_s * pp.FS_IN))
    next_step = seq_first + step_pkts
    live = []
    for seq, r, raw, rssi in ev:
        while seq >= next_step:                           # steps happen on the TX clock, as in real time
            clock.t = (next_step - seq_first) / pp.FS_IN
            st = eng.step()
            if st["status"] == "ok":
                w = eng.last_window
                live.append(dict(seq0=st["window_seq0"], X=w["X"], P=w["P"], rssi=w["rssi"], out=st))
            next_step += step_pkts
        clock.t = (seq - seq_first) / pp.FS_IN
        buf.push(r, seq, raw, rssi)
    per_rx = {r: pp.records_from_recording(cw.load(folder / f"RX{r}.bin")) for r in pp.RX_IDS}
    grid = pp.build_grid(per_rx)
    dx = dp = dr = 0.0
    same_label = same_event = 0
    dprob = 0.0
    for L in live:
        w = pp.window(grid, L["seq0"] - grid["seq0"], predictor.window_s)
        off = predictor.predict(w["X"], w["rssi"], w["P"])
        dx = max(dx, float(np.abs(w["X"] - L["X"]).max()))
        dp = max(dp, float(np.abs(np.angle(np.exp(1j * (w["P"] - L["P"])))).max()))
        dr = max(dr, float(np.abs(w["rssi"] - L["rssi"]).max()))
        same_label += off["label"] == L["out"]["label"]
        same_event += off["event"] == L["out"]["event"]
        dprob = max(dprob, abs(off["fall_prob"] - L["out"]["fall_prob"]),
                    max(abs(off["probs"][k] - L["out"]["probs"][k]) for k in off["probs"]))
    n = len(live)
    return dict(session=folder.name, windows=n, max_abs_diff_X=dx, max_abs_diff_P=dp, max_abs_diff_rssi=dr,
                max_abs_diff_prob=dprob, same_label=same_label, same_event=same_event,
                identical=bool(n and same_label == n and same_event == n and dprob < 1e-6))
