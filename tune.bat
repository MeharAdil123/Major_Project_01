@echo off
REM Small learning-rate / weight-decay / batch-size search for the full CNN-BiLSTM, fall task, LOSO, 3 seeds.
REM Choose the setting with the highest val_f1_mean in results\benchmark\tuning.csv (NOT macro_f1_mean).
set COMMON=--task fall --protocol loso --models cnn_bilstm --aug strohmayer --tta adabn --hybrid --seeds 0 1 2
for %%L in (0.0003 0.001 0.003) do (
  for %%W in (0.001 0.01 0.05) do (
    python benchmark_deep.py %COMMON% --lr %%L --wd %%W
  )
)
python benchmark_deep.py %COMMON% --batch_size 32
python benchmark_deep.py %COMMON% --batch_size 128
python benchmark_deep.py %COMMON% --patience 10
echo Done. Open results\benchmark\tuning.csv
