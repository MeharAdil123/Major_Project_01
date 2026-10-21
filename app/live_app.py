"""Live monitoring dashboard (STARTER - Track D owns and improves this file).

    streamlit run app/live_app.py -- --serial
    streamlit run app/live_app.py -- --replay-dir data_synth/raw --pattern "SYNTH_P1_*" --models models_synth --loop

Everything shown comes from engine.latest / engine.history (see app/engine.py for the dict).
"""
import sys
import time
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from app import engine as E  # noqa: E402

st.set_page_config(page_title="WiFi-CSI Room Monitor", layout="wide")


@st.cache_resource
def get_engine(argv: tuple):
    args = E.parser().parse_args(list(argv))
    eng, _ = E.build(args)
    return eng


eng = get_engine(tuple(sys.argv[1:]))
st.title("Camera-free room monitor (Wi-Fi CSI)")
if eng.pred.synthetic:
    st.warning("Model trained on SYNTHETIC data - for software testing only.")

top = st.empty()
mid = st.empty()
bottom = st.empty()

ICON = {"empty": "🟢 Empty", "sit": "🪑 Sitting", "stand": "🧍 Standing", "walk": "🚶 Walking",
        "lie": "🛏️ Lying", "uncertain": "❔ Uncertain", "unknown": "⚠️ Unknown"}

while True:
    s = eng.latest
    hist = list(eng.history)
    with top.container():
        c1, c2, c3, c4 = st.columns(4)
        lab = s.get("label_smoothed", "unknown")
        c1.metric("Room", "Empty" if lab == "empty" else ("Occupied" if lab not in ("unknown", "uncertain") else "?"))
        c2.metric("Activity", ICON.get(lab, lab))
        c3.metric("Confidence", f"{s.get('confidence', 0):.0%}")
        c4.metric("System", s.get("status", "-"))
        alerts = [h for h in hist if h.get("alert")]
        if alerts and s.get("t", 0) - alerts[-1]["t"] < 15:
            st.error(f"FALL ALERT at t={alerts[-1]['t']} s")
    with mid.container():
        c1, c2 = st.columns([2, 1])
        if s.get("probs"):
            c1.bar_chart(s["probs"])
        rx = s.get("rx", {})
        c2.write({k: f"{v['rate']} pkt/s, RSSI {v['rssi']}" for k, v in rx.items()})
        if s.get("reason"):
            c2.info(s["reason"])
        if s.get("source"):
            c2.caption(f"replaying: {s['source']}")
    with bottom.container():
        if hist:
            st.line_chart({"motion": [h.get("motion", 0) or 0 for h in hist[-240:]],
                           "fall_prob": [h.get("fall_prob", 0) or 0 for h in hist[-240:]]})
    time.sleep(0.5)
