# Track D: Live demo, dashboard, documentation (owner: Nihar)

**Goal:** a reliable live dashboard for the 14:00 demo, a backup replay demo, and a clean README/report.

**Owns:** `app/` (`engine.py` is shared: change only with care; `live_app.py` is yours), `README.md`, `docs/REPORT.md`, slides if needed.
**Input:** Format 3 (`models/`) + the live boards (or replayed takes). Tonight: `models_synth` + `data_synth/raw`.
**Output:** `streamlit run app/live_app.py -- --serial` (live) and `-- --replay-dir ...` (backup).

## Tonight
1. `pip install -r host/requirements.txt`, `scripts/pipeline.sh synth`, then
   `streamlit run app/live_app.py -- --replay-dir data_synth/raw --pattern "SYNTH_P1_*" --models models_synth --loop`.
2. Make the dashboard demo-ready: big room status (Empty/Occupied), current activity with icon, confidence bar, a clear **uncertain** state, fall alert banner + sound, event history table (time, activity changes, alerts), system health (packets/s and RSSI per receiver, model trained-at, synthetic warning).
3. A "How it works" side panel (one diagram: TX → wall/room → 2 RX → CSI → windows → model → state) for the panel.
4. README: what it is, hardware, how to install/run each step (`scripts/pipeline.sh`), results placeholder, limitations, privacy.

## Tomorrow
- 11:00: test with real replayed takes from Mohith (`--replay-dir data/raw`) and the first real model.
- 12:30–13:30: rehearse on the real boards with Mohith. Keep the replay demo ready as backup if the radio misbehaves in the panel room.
- 13:30: fill README results from `results/summary.json`; final push.

## Done when
- Live dashboard runs 10 minutes on the real boards without errors; backup replay works offline.
- README lets a stranger install and run the pipeline.

## Claude Code prompt
> Read docs/CONTRACTS.md, app/engine.py and app/live_app.py. Improve app/live_app.py into a clean Streamlit dashboard for a live panel demo: large room status and activity with icons, confidence, an explicit "uncertain" state, fall alert banner with sound, an event-history table built from engine.history (only record changes), system health per receiver, and a "How it works" panel. Keep using engine.latest/engine.history; do not change the Predictor interface or pipeline/preprocess.py. Test with: streamlit run app/live_app.py -- --replay-dir data_synth/raw --pattern "SYNTH_P1_*" --models models_synth --loop
