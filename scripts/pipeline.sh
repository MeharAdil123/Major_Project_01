#!/usr/bin/env bash
# One entry point for the pipeline (v2). Run from the repo root. Python = the project venv unless PY is set.
#   scripts/pipeline.sh audit            # read-only raw-data audit (counts, decode, drift check)
#   scripts/pipeline.sh dataset          # data/raw -> data/processed + data/features for 2, 3, 4 s windows
#   scripts/pipeline.sh phase4           # model comparison chain (long; resumable; run under systemd-inhibit)
#   scripts/pipeline.sh train            # final models on all subjects -> models/ (Format 3)
#   scripts/pipeline.sh consistency      # live vs offline check on real takes
#   scripts/pipeline.sh test             # unit tests
#   scripts/pipeline.sh replay [glob]    # dashboard replaying recorded takes (backup demo, no boards)
#   scripts/pipeline.sh demo             # dashboard on the live boards (laptop Wi-Fi + Bluetooth OFF, D-032)
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PY:-../hostenv/bin/python}
ST=${ST:-../hostenv/bin/streamlit}
case "${1:-}" in
  audit)       $PY scripts/audit_raw.py --decode --baseline-csv results/audit/raw_takes.csv --rssi-tol 3 ;;
  dataset)     for w in 2 3 4; do $PY -m pipeline.build_dataset --win $w; done ;;
  phase4)      bash scripts/phase4_overnight.sh ;;
  train)       $PY -m ml.train_final ;;
  consistency) $PY scripts/phase5_consistency.py ;;
  test)        $PY -m pytest ;;
  replay)      $ST run app/live_app.py -- --replay-dir data/raw --pattern "${2:-*S6_E2*}" --loop ;;
  demo)        $ST run app/live_app.py -- --serial ;;
  *) sed -n '2,11p' "$0"; exit 1 ;;
esac
