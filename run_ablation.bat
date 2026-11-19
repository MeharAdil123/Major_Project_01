@echo off
REM Ablation study for the report. Run from the "WiFi CSI Agent" folder.
REM Every result is appended to results\benchmark\summary.csv (and fall_alarm.csv).
REM Uses the fast models (cnn_bilstm, se_tcn). WiFlexFormer is slow on CPU: run it separately afterwards with the best settings.

echo ===== STAGE 1: fall detection (binary), one improvement at a time =====
python benchmark_deep.py --task fall --models cnn_bilstm se_tcn
python benchmark_deep.py --task fall --models cnn_bilstm se_tcn --tta adabn
python benchmark_deep.py --task fall --models cnn_bilstm se_tcn --aug strohmayer
python benchmark_deep.py --task fall --models cnn_bilstm se_tcn --hybrid
python benchmark_deep.py --task fall --models cnn_bilstm se_tcn --aug strohmayer --tta adabn --hybrid

echo ===== STAGE 2: same ablation on the 5-class events task =====
python benchmark_deep.py --task events --models cnn_bilstm se_tcn --tta adabn
python benchmark_deep.py --task events --models cnn_bilstm se_tcn --aug strohmayer
python benchmark_deep.py --task events --models cnn_bilstm se_tcn --hybrid
python benchmark_deep.py --task events --models cnn_bilstm se_tcn --aug strohmayer --tta adabn --hybrid

echo ===== STAGE 3: full combination on presence and state =====
python benchmark_deep.py --task presence --models cnn_bilstm se_tcn --aug strohmayer --tta adabn --hybrid
python benchmark_deep.py --task state    --models cnn_bilstm se_tcn --aug strohmayer --tta adabn --hybrid

echo ===== DONE - open results\benchmark\summary.csv =====
