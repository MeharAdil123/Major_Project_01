#!/usr/bin/env bash
# Reproduce the final state from the raw recordings, without touching the committed outputs.
# Run from the repo root:  scripts/pipeline.sh reproduce      (11 min on an Intel i3-7020U, 2026-10-23)
#   0. raw recordings unchanged: SHA-256 of every file listed in results/audit/raw_sha256.txt
#   1. raw-data audit (read-only)                                   <1 min
#   2. 4 s dataset from data/raw into a scratch folder              ~7 min
#   3. final models retrained into a scratch folder                 <1 min
#   4. compare with data/features and models/ (scripts/reproduce_check.py)
#   5. live = offline consistency on 12 real takes, unit tests
# The full model comparison (Phase 4, ~7 h) is `scripts/pipeline.sh phase4`; it is not part of this run.
# Logs: results/reproduction/*.log
set -uo pipefail
cd "$(dirname "$0")/.."
PY=${PY:-../hostenv/bin/python}
OUT=${OUT:-$(mktemp -d /tmp/wifi_csi_repro.XXXX)}
LOG=results/reproduction
mkdir -p "$LOG" "$OUT/processed" "$OUT/features" "$OUT/models"
export PYTHONWARNINGS="ignore::FutureWarning"
run() {   # run <name> <command...>
  local name=$1; shift
  local t0=$(date +%s)
  echo "$(date -Is) START $name :: $*" | tee -a "$LOG/reproduce.log"
  "$@" > "$LOG/$name.log" 2>&1; local rc=$?
  echo "$(date -Is) END   $name rc=$rc ($(( $(date +%s) - t0 )) s)" | tee -a "$LOG/reproduce.log"
  return $rc
}
echo "$(date -Is) ==== reproduction, scratch $OUT, git $(git rev-parse --short HEAD) ====" | tee -a "$LOG/reproduce.log"
run checksums bash -c 'cd data/raw && sha256sum -c --quiet ../../results/audit/raw_sha256.txt && echo "all $(wc -l < ../../results/audit/raw_sha256.txt) files OK"'
run audit       $PY scripts/audit_raw.py --decode --baseline-csv results/audit/raw_takes.csv --rssi-tol 3
run dataset_4s  $PY -m pipeline.build_dataset --win 4 --processed "$OUT/processed" --features "$OUT/features"
run train       $PY -m ml.train_final --models "$OUT/models"
run compare     $PY scripts/reproduce_check.py "$OUT/features" "$OUT/models"
run consistency $PY scripts/phase5_consistency.py
run tests       $PY -m pytest -q -p no:warnings
echo "$(date -Is) ==== done (scratch outputs left in $OUT) ====" | tee -a "$LOG/reproduce.log"
