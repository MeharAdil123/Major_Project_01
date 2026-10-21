#!/usr/bin/env bash
# One entry point for the whole pipeline. Run from the repo root.
#   scripts/pipeline.sh synth     # fake dataset -> dataset -> train (tests the software, no hardware)
#   scripts/pipeline.sh dataset   # data/raw -> data/processed
#   scripts/pipeline.sh train     # data/processed -> models/ + results/
#   scripts/pipeline.sh inspect <session folder>
#   scripts/pipeline.sh demo      # live dashboard on the real boards
#   scripts/pipeline.sh replay    # dashboard replaying recorded takes (backup demo)
set -euo pipefail
PY=${PY:-python3}
case "${1:-}" in
  synth)
    $PY -m host.tests.make_synthetic_dataset --out data_synth/raw --subjects 3
    $PY -m pipeline.build_dataset --raw data_synth/raw --out data_synth/processed
    $PY -m ml.train --data data_synth/processed --models models_synth --results results_synth ;;
  dataset) $PY -m pipeline.build_dataset ;;
  train)   $PY -m ml.train ;;
  inspect) $PY host/csi_inspect.py "$2" ;;
  demo)    streamlit run app/live_app.py -- --serial ;;
  replay)  streamlit run app/live_app.py -- --replay-dir data/raw --pattern "${2:-*}" --loop ;;
  *) sed -n '2,9p' "$0"; exit 1 ;;
esac
