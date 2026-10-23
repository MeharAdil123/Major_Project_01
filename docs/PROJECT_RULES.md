# Project rules

Working rules for anyone maintaining or extending this project. Decisions that refine them are in
[`decisions/DECISIONS.md`](decisions/DECISIONS.md); numbers below are referenced from there as "rule N".

## Layout
- Repository: `wifi-csi-har/`. Python virtual environment: `../hostenv` (see the README for setup).
- Raw recordings: `data/raw/` (202 takes from 22 Oct 2026, subjects S1–S6 plus empty-room takes). They cannot be re-recorded.
- Derived data: `data/processed/`, `data/features/`; trained models: `models/`; results: `results/`.

## Rules
1. **Raw data is read-only.** Never modify, move, rename or delete anything in `data/raw/` or `data/raw/_rejected/`. Corrections go in `config/take_overrides.csv`, never in a take's `meta.json`.
2. **Nothing is deleted.** Unneeded files go to `../_archive/<YYYYMMDD>/` with a line in `../_archive/ARCHIVE_LOG.md` (what, from where, why), after the team has agreed on the list.
3. **Hardware changes are deliberate.** Flashing, erasing or reconfiguring a board, and `power ... save` on the TX, are done only on purpose and recorded. Opening the TX serial port resets the TX.
4. **What goes into git.** Code, configuration, documentation, small result tables, model metadata (`model_meta.json`) and firmware images under `releases/**/*.bin`. **Never** recorded data (`data/**`, raw `RX1.bin`/`RX2.bin`), `.npz` arrays, `.joblib` or other model weights, or credentials. Recordings are not uploaded to any online service.
5. **No unsupported numbers.** Every number in a report comes from a script that was run; the command and its log file are kept next to the result.
6. **Evaluation is leave-one-subject-out** (S1–S6, 6 folds; D-028), never random window splits. Scalers, feature selection and hyper-parameter search live inside the training folds (nested). Empty-room takes are dealt to folds take by take.
7. **Synthetic data** is labelled SYNTHETIC everywhere and never mixed with real results.
8. **Frozen interfaces** (`Predictor.predict(X, rssi, P)` output dict, `pipeline/preprocess.py` shared by offline and live code, Formats 1/2/3 in [`CONTRACTS.md`](CONTRACTS.md)) change only with a version bump (`PREPROC_VERSION`, `FEATURES_VERSION`) and an entry in `decisions/DECISIONS.md`.
9. Work is done in phases with a review point at the end of each.
10. Python packages are installed only inside the virtual environment and pinned in `requirements.txt` (one file, repo root).
11. **RF hygiene during recording and live use (D-032):** laptop Wi-Fi and Bluetooth off, phones in airplane mode.

## After each piece of work
Update `docs/STATUS.md` (date, what was done, verified results with log paths, open problems, next step) and record decisions in `docs/decisions/DECISIONS.md`. Work happens on a branch; `main` receives merges only.
