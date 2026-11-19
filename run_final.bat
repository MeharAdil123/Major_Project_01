@echo off
REM Final runs for the report. Run from the "WiFi CSI Agent" folder (takes several hours).
REM 3 seeds everywhere so differences can be checked against seed noise.
REM "full" = --aug strohmayer --tta adabn --hybrid

echo ===== A: features-only control (fast) =====
python benchmark_deep.py --task fall     --models feat_only --hybrid --seeds 0 1 2
python benchmark_deep.py --task events   --models feat_only --hybrid --seeds 0 1 2
python benchmark_deep.py --task state    --models feat_only --hybrid --seeds 0 1 2
python benchmark_deep.py --task presence --models feat_only --hybrid --seeds 0 1 2

echo ===== B: baseline vs full, 3 seeds =====
python benchmark_deep.py --task fall   --models cnn_bilstm se_tcn --seeds 0 1 2
python benchmark_deep.py --task fall   --models cnn_bilstm se_tcn --seeds 0 1 2 --aug strohmayer --tta adabn --hybrid
python benchmark_deep.py --task events --models cnn_bilstm se_tcn --seeds 0 1 2
python benchmark_deep.py --task events --models cnn_bilstm se_tcn --seeds 0 1 2 --aug strohmayer --tta adabn --hybrid
python benchmark_deep.py --task state  --models cnn_bilstm se_tcn --seeds 0 1 2
python benchmark_deep.py --task state  --models cnn_bilstm se_tcn --seeds 0 1 2 --aug strohmayer --tta adabn --hybrid

echo ===== C: presence (improvements hurt with dynamic features; try all features) =====
python benchmark_deep.py --task presence --models cnn_bilstm se_tcn --seeds 0 1 2
python benchmark_deep.py --task presence --models cnn_bilstm se_tcn --seeds 0 1 2 --hybrid --features all

echo ===== D: base-paper model with the full recipe (slow) =====
python benchmark_deep.py --task fall --models wiflexformer --aug strohmayer --tta adabn --hybrid

echo ===== DONE - send results\benchmark\summary.csv and fall_alarm.csv =====
