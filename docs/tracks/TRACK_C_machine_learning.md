# Track C: Models and evaluation (owner: Mehar)

**Goal:** honest, held-out results for activity recognition, presence and fall detection, and the model files for the demo.

**Owns:** `ml/` (`features.py`, `train.py`, `predict.py` interface), `results/` (metrics + figures).
**Input:** Format 2 (`windows_state.npz`, `windows_event.npz`). Tonight: `data_synth/processed`.
**Output:** Format 3 (`models/state_rf`, `models/event_rf`, `results/*.json`, `results/*_confusion.png`).

## Tonight (synthetic data, only to get the code ready)
1. `scripts/pipeline.sh synth` runs; read `results_synth/state_metrics.json`.
2. Add `ml/report.py`: one figure/table set for the report: per-class P/R/F1 table, confusion matrices (state, event), presence sensitivity/specificity, feature importances (top 15), per-fold (per-subject) accuracy.
3. Add an **ablation** in `ml/train.py` or a new `ml/ablation.py`: RX1 only vs RX2 only vs both; static features only vs motion features only. This shows *why* the design choices matter (two receivers, etc.).
4. Optional, only after 1–3: a small 1-D CNN (PyTorch) on `X` with the same LOSO folds, wrapped behind `ml/predict.py` with the same `predict()` call. Keep the random forest as the default unless the CNN is clearly better on LOSO.

## Tomorrow
- 10:30 onwards: train on partial data as it arrives (check the code works on real data).
- 12:00: final training on the frozen dataset → `models/`, `results/`. Hand `models/` to Nihar (copy; joblib files are not committed).
- 12:00–13:00: write the results section: numbers, confusion matrices, limitations (one room, 3 volunteers, simulated falls).

## Done when
- `results/summary.json` with LOSO accuracy and macro-F1 for states, presence sensitivity/specificity, fall sensitivity and false-alarm share.
- Ablation table. Models load in `ml.predict.Predictor`.

## Rules
- **Never** use random train/test splits of windows (they leak). Always group by subject (LOSO) or at least by take.
- Report exactly what was measured; mark synthetic results as synthetic.

## Claude Code prompt
> Read docs/CONTRACTS.md and ml/train.py. Write ml/report.py that loads results/*.json and the models and produces a markdown table + figures in results/report/ (per-class P/R/F1, confusion matrices, presence metrics, top features, per-subject accuracy). Then write ml/ablation.py that reuses the LOSO evaluation from ml/train.py for: RX1-only features, RX2-only features, both; static-only vs motion-only features. Test on data_synth/processed. Do not change the Predictor.predict() input/output.
