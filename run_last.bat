@echo off
REM Final experiment set. Run from the "WiFi CSI Agent" folder. About 4-5 hours in total.
REM The first run of each --input builds a cache file in data\ (a few minutes, once).

echo ===== A: does keeping the static signal help? (input type x protocol) =====
for %%T in (state presence fall) do (
  for %%P in (group loso) do (
    python benchmark_deep.py --task %%T --protocol %%P --models cnn_bilstm se_tcn --input static
    python benchmark_deep.py --task %%T --protocol %%P --models cnn_bilstm se_tcn --input raw_amp
  )
)

echo ===== B: dual-receiver ablation (RX1 only / RX2 only; "both" already done), 3 seeds =====
for %%T in (fall state) do (
  for %%R in (1 2) do (
    python benchmark_deep.py --task %%T --models cnn_bilstm --rx %%R --seeds 0 1 2 --aug strohmayer --tta adabn --hybrid
  )
)

echo ===== C: official WiFlexFormer on raw amplitude, as in the base paper (slow, ~1.5-3 h) =====
python benchmark_deep.py --task fall --protocol group --models wiflexformer_official --input raw_amp

echo ===== DONE - send results\benchmark\summary.csv and fall_alarm.csv =====
