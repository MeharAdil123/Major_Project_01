@echo off
REM In-domain comparison (matches how Strohmayer reports his ~98% numbers: same room/people,
REM unseen recordings). Grouped by take, so overlapping windows cannot leak. Run from "WiFi CSI Agent".
REM "full" = --aug strohmayer --tta adabn --hybrid

for %%T in (presence state events fall) do (
  python benchmark_deep.py --task %%T --protocol group --models cnn_bilstm se_tcn
  python benchmark_deep.py --task %%T --protocol group --models cnn_bilstm se_tcn --aug strohmayer --tta adabn --hybrid
)

REM Base-paper model in the same in-domain setting (slow on CPU)
python benchmark_deep.py --task state --protocol group --models wiflexformer
python benchmark_deep.py --task fall  --protocol group --models wiflexformer

REM Leakage demo for the report: same model, random window split
python benchmark_deep.py --task state --protocol random --models cnn_bilstm se_tcn

echo ===== DONE - send results\benchmark\summary.csv =====
