#!/usr/bin/env bash
# Phase 4 overnight chain (resumable). Run from the repo root, normally via:
#   systemd-run --user --unit=csi-phase4 --working-directory=$PWD \
#     systemd-inhibit --what=sleep:idle:handle-lid-switch --who=wifi-csi-har --why="Phase 4 runs" --mode=block \
#     bash scripts/phase4_overnight.sh
# Every step skips work whose result file already exists, so re-running continues where it stopped.
# Log: results/phase4/overnight.log (one START/END line per step with exit code).
set -u
cd "$(dirname "$0")/.."
PY=../hostenv/bin/python
LOG=results/phase4/overnight.log
mkdir -p results/phase4
exec 9>results/phase4/.overnight.lock
flock -n 9 || { echo "another phase4_overnight.sh is running" | tee -a "$LOG"; exit 1; }
export PYTHONWARNINGS="ignore::FutureWarning"

step() {          # step <name> <command...>
  local name=$1; shift
  echo "$(date -Is) START $name :: $*" >> "$LOG"
  "$@" >> "results/phase4/step_${name}.log" 2>&1
  local rc=$?
  echo "$(date -Is) END   $name rc=$rc" >> "$LOG"
}

echo "$(date -Is) ==== chain start (pid $$) ====" >> "$LOG"
step trackA_3s     $PY scripts/phase4_track_a.py --wins 3 --tasks events state presence --featsets dynamic all
step trackA_2s4s   $PY scripts/phase4_track_a.py --wins 2 4 --tasks events state presence --featsets dynamic
step stream_3s     $PY scripts/build_stream.py --win 3
step choose_window $PY scripts/phase4_choose_window.py
WIN=$($PY -c "import json;print(json.load(open('results/phase4/chosen_window.json'))['chosen'][:-1])" 2>/dev/null || echo 3)
EV=$($PY -c "import json;print(json.load(open('results/phase4/chosen_window.json'))['best_model_per_task']['events'])" 2>/dev/null || echo rf)
echo "$(date -Is) chosen window ${WIN} s, best events model ${EV}" >> "$LOG"
[ "$WIN" != "3" ] && step stream_${WIN}s $PY scripts/build_stream.py --win "$WIN"
step pertake_dynamic $PY scripts/phase4_pertake.py --model "$EV" --featset dynamic --win "$WIN"
step pertake_all     $PY scripts/phase4_pertake.py --model "$EV" --featset all --win "$WIN"
step ablations_events $PY scripts/phase4_ablations.py --tasks events
for t in events state presence; do
  step trackB_$t $PY scripts/phase4_track_b.py --task $t --win "$WIN"
done
step trackC_events $PY scripts/phase4_track_c.py --task events --win "$WIN"
step ablations_state_presence $PY scripts/phase4_ablations.py --tasks state presence --core-only
step trackC_state  $PY scripts/phase4_track_c.py --task state --win "$WIN"
step trackA_summary $PY scripts/phase4_track_a.py --wins 3 --tasks events --featsets dynamic --models logreg
echo "$(date -Is) ==== chain end ====" >> "$LOG"
