"""Live monitoring dashboard (Streamlit). Runs on replay (no boards) and on live boards.

    streamlit run app/live_app.py -- --replay-dir data/raw --pattern "*S6_E2*" --loop     # backup demo
    streamlit run app/live_app.py -- --serial                                             # boards (D-032: laptop Wi-Fi + Bluetooth OFF)

Everything shown comes from app/engine.py (engine.latest / history / events / heatmap()). Panels refresh
once per second (st.fragment). No raw CSI is stored; predictions are logged to logs/live_*.jsonl.
"""
import sys
import time
from pathlib import Path

import numpy as np
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from app import engine as E  # noqa: E402

st.set_page_config(page_title="WiFi-CSI Room Monitor", layout="wide", page_icon="📡")

ICON = {"empty": "🟢 Empty", "sit": "🪑 Sitting", "stand": "🧍 Standing", "walk": "🚶 Walking", "lie": "🛏️ Lying",
        "uncertain": "❔ Uncertain", "unknown": "⚠️ Unknown"}
EVENT = {"fall": "🚨 Fall", "sit_down": "⬇️ Sit down", "stand_up": "⬆️ Stand up", "bend_pick": "↘️ Bend & pick",
         "none": "—"}


@st.cache_resource
def get_engine(argv: tuple):
    """The engine runs in its own process (app/engine_proc.py, D-057), so page reruns never slow it down."""
    from app.engine_proc import EngineProxy
    args = E.parser().parse_args(list(argv))
    return EngineProxy(argv, args.models), args


eng, args = get_engine(tuple(sys.argv[1:]))
pred = eng.pred
mode = "LIVE (boards)" if args.serial else "REPLAY (recorded takes)"

st.title("📡 Camera-free room monitor — Wi-Fi CSI")
st.caption(f"Mode: **{mode}** · window {pred.window_s:g} s, step {E.STEP_S:g} s · "
           f"fall alarm: ≥ {pred.alarm['k']} of the last {pred.alarm['n']} windows with P(fall) ≥ {pred.alarm['theta']:g}, "
           f"{pred.alarm['cooldown_s']:g} s cooldown")
if pred.synthetic:
    st.warning("Models trained on SYNTHETIC data — for software testing only.")
if args.serial:
    st.info("RF hygiene (D-032): laptop Wi-Fi and Bluetooth must be OFF while monitoring.")
else:
    st.warning("Replay of recorded takes. These takes were part of the training data of the final models, so the "
               "predictions shown are **in-sample** — a demo of the system, not a test result (test results: "
               "leave-one-subject-out, results/REPORT.md).")

with st.sidebar:
    st.header("Environment check")
    st.write("Records the EMPTY room for 60 s and compares it with the training empty rooms. "
             "Leave the room empty while it runs.")
    if st.button("Start empty-room check (60 s)"):
        eng.start_env_check(60)
    st.divider()
    st.header("Test markers")
    st.caption("Live test: choose what you are about to do, press the button, then do it. Logged with the time.")
    mk = st.selectbox("Activity", ["empty (nobody inside the tape)", "stand at A", "sit_down at A", "stand_up at A",
                                   "walk path1", "walk path2", "bend_pick at C", "fall on mattress M",
                                   "RX2 unplugged", "RX2 replugged", "other"])
    if st.button("Mark start"):
        m = eng.mark(mk)
        st.success(f"marked '{mk}' at t = {m['t']:.1f} s ({m['wall']})")
    st.divider()
    st.header("Model")
    for task in ("presence", "state", "events", "fall_alarm"):
        m = pred.meta.get(task)
        if not m:
            continue
        lo = m.get("loso") or {}
        txt = (f"LOSO macro-F1 {lo['macro_f1_mean']:.3f} ± {lo['macro_f1_std']:.3f}" if lo else
               f"chain: {m.get('loso_chain', {}).get('falls', '?')}/{m.get('loso_chain', {}).get('fall_takes', '?')} falls (LOSO)")
        st.write(f"**{task}** — {m['model'][:28]}  \n{txt}  \ntrained {m['trained_at']}")
    st.caption(f"preprocess {pred.meta['events']['preproc_version']} · features {pred.meta['events']['features_version']} · "
               f"Predictor p2 · git {pred.meta['events'].get('git_commit')}")


def to_rgb(a, vmin, vmax, cmap="RdBu_r"):
    """2-D array -> uint8 RGB image via a matplotlib colormap (no figure: cheap enough for the live loop)."""
    import matplotlib
    x = np.clip((np.asarray(a, np.float32) - vmin) / (vmax - vmin), 0, 1)
    return (matplotlib.colormaps[cmap](x)[..., :3] * 255).astype(np.uint8)


@st.fragment(run_every=2.0)
def heat_panel():
    h = eng.heatmap(6.0)
    if h is None:
        st.caption("heatmaps: waiting for packets")
        return
    st.caption("Last 6 s, newest on the right · rows = 114 sub-carriers (−58 bottom … +58 top) · "
               "amplitude: dB vs its 6 s median (±6 dB) · phase: sanitised phase minus its 6 s mean (±1.5 rad)")
    c = st.columns(2)
    for r in range(2):
        amp = np.repeat(np.flipud(h["amp_db"][r].T), 2, axis=0)
        ph = np.repeat(np.flipud(h["phase"][r].T), 2, axis=0)
        c[r].image(to_rgb(amp, -6, 6), caption=f"RX{r + 1} amplitude", use_container_width=True)
        c[r].image(to_rgb(ph, -1.5, 1.5), caption=f"RX{r + 1} sanitised phase", use_container_width=True)


@st.fragment(run_every=1.0)
def live_panel():
    s = eng.latest
    hist = list(eng.history)
    lab = s.get("label_smoothed", "unknown")
    status = s.get("status", "-")
    c1, c2, c3, c4, c5 = st.columns(5)
    room = "Empty" if lab == "empty" else ("Occupied" if lab not in ("unknown", "uncertain") else "?")
    c1.metric("Room", room, f"P(occupied) {s.get('presence_prob', 0):.2f}" if "presence_prob" in s else None)
    c2.metric("Activity", ICON.get(lab, lab))
    c3.metric("Confidence", f"{s.get('confidence', 0):.0%}")
    c4.metric("System", status.upper())
    last = eng.events[-1] if eng.events else None
    c5.metric("Last event", EVENT.get(last["kind"].lower() if last["kind"] != "FALL" else "fall", last["kind"]) if last else "—",
              f"t = {last['t']:.0f} s" if last else None)
    alerts = [e for e in eng.events if e["kind"] == "FALL"]
    if alerts and s.get("t", 0) - alerts[-1]["t"] < 15:
        st.error(f"🚨 FALL ALERT at t = {alerts[-1]['t']:.1f} s — check on the person", icon="🚨")
    if s.get("reason"):
        st.warning(f"{status}: {s['reason']}")
    if s.get("source"):
        st.info(f"Replaying **{s['source']}** · true label now: **{s.get('truth')}** · predicted: **{lab}**"
                f" · event: {EVENT.get(s.get('event', 'none'), s.get('event'))}")
    env = eng.env
    if env:
        if env.get("state") == "recording":
            st.info(f"Environment check: recording empty room … {100 * env['progress']:.0f} % ({env['windows']} windows)")
        elif env.get("state") == "done":
            (st.success if env["verdict"] == "ok" else st.error)(
                f"Environment check: **{env['verdict']}**" + (" — " + "; ".join(env["reasons"]) if env["reasons"] else ""))
            st.caption(env["note"])
        else:
            st.warning(f"Environment check unavailable: {env.get('reason')}")

    left, right = st.columns([3, 2])
    with right:
        ok = [x for x in hist[-240:] if x.get("status") == "ok"]
        if ok:
            st.caption("Last 2 minutes (one point per 0.5 s step)")
            st.line_chart({"P(fall)": [x["fall_prob"] for x in ok], "P(occupied)": [x["presence_prob"] for x in ok],
                           "motion ×10": [10 * x["motion"] for x in ok]}, height=180)
            st.line_chart({k: [x["rx"][k]["rssi"] for x in ok] for k in ("RX1", "RX2")}, height=140)
        rx = s.get("rx", {})
        fmt = lambda x, f="{:.0f}": "—" if x is None else f.format(x)  # noqa: E731
        st.table({k: {"packets/s": fmt(v.get("rate")), "loss %": fmt(v.get("loss_pct"), "{:.1f}"),
                      "RSSI dBm": fmt(v.get("rssi")), "last packet (s ago)": fmt(v.get("age_s"), "{:.2f}"),
                      **({"connected": str(v.get("connected")), "reconnects": fmt(v.get("reconnects"))} if args.serial else {})}
                  for k, v in rx.items()})
    with left:
        st.subheader("Event history")
        rows = [{"t (s)": f"{e['t']:.1f}", "event": ("FALL ALARM" if e["kind"] == "FALL" else
                                                    (f"▶ {e['label']}" if e["kind"] == "MARK" else e["kind"])),
                 "probability": f"{e.get('fall_prob', e.get('p', 0)):.2f}", "take": (e.get("source") or "")[9:],
                 "true label": e.get("truth") or "—"} for e in list(eng.events)[-8:][::-1]]
        if rows:
            st.table(rows)
        else:
            st.caption("no events yet")


live_panel()
heat_panel()

with st.expander("How it works"):
    st.markdown("""
**TX** (ESP32, 8 dBi patch, ch 11 HT40, 200 packets/s) → **room** (the body changes the multipath) → **RX1 / RX2** (ESP32-S3, raw CSI, 114 sub-carriers) →
**CSI**: amplitude normalised per packet (removes 6 dB scale shifts), sanitised phase (per-packet slope/offset removed), RX1/RX2 aligned by TX sequence number →
**windows**: 4 s, anti-alias filtered to 100 Hz, new window every 0.5 s, rejected if > 20 % packets missing →
**features**: 50 *dynamic* features (motion, band power, temporal variation, phase variation, cross-RX) — static channel shape is not used because it encodes *where* a person is →
**models**: presence (logistic regression), state (extra trees), events (SVM), fall alarm (calibrated SVM; ≥ 2 of 3 windows with P(fall) ≥ 0.5).
Evaluation: leave-one-subject-out over 6 volunteers (`results/REPORT.md`).
""")
with st.expander("Limitations"):
    st.markdown("""
- One room (library hall), one layout, **6 volunteers**; the demo room is different → run the environment check first.
- Falls were **simulated on a mattress**, all at **one spot**; detection elsewhere in the room is not shown by the data.
- Leave-one-subject-out results: events macro-F1 0.54, state 0.57, presence 0.70; fall alarm caught **≈ half of the falls** (21/42) with false alarms on ≈ 1 in 14 look-alike movements.
- A person **sitting or standing very still** can look like an empty room.
- Recognition depends on position relative to the two links (best near RX1).
- No video ground truth; **not a medical device**, not clinically validated.
""")
