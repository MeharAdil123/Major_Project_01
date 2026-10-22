# CLAUDE.md — standing rules for the WiFi-CSI HAR project

Put this file at `~/WiFi_CSI_Final/CLAUDE.md`. Claude Code reads it at the start of every session.

## Where things are
- Working repo: `~/WiFi_CSI_Final/wifi-csi-har` (git). Raw data: `wifi-csi-har/data/raw/` (125 takes, irreplaceable).
- Python venv: `~/WiFi_CSI_Final/hostenv`. ESP-IDF v5.5.5: `~/WiFi_CSI_Final/esp/esp-idf-v5.5.5` (`export.sh` broken).
- Full project background: `docs/context/PROJECT_CONTEXT.md` (copied from the handover zip). Read it before planning.

## Hard rules
1. **Never modify, move, rename or delete anything in `data/raw/` or `data/raw/_rejected/`.** Treat raw data as read-only. Derived data goes in `data/processed/`, `data/features/`, `models/`, `results/`.
2. **Never delete files.** To clean up, move unneeded files to `~/WiFi_CSI_Final/_archive/<YYYYMMDD>/` with a line in `_archive/ARCHIVE_LOG.md` (what, from where, why). Show the move list and wait for approval before moving.
3. **Never flash, erase or reconfigure a board, and never send `power ... save` to the TX,** unless the user says so in this session. Reading a serial port is fine; tell the user first, because opening the TX port resets it.
4. **Never commit raw data, `.bin`, `.npz`, `.joblib`, model weights, or any token/password.** Never push to GitHub without the user asking. Never upload recordings to any online service.
5. **Never fabricate results.** Every number in a report comes from a script that ran in this session; keep the command and its output (log file) next to the result.
6. **Evaluation:** leave-one-subject-out only (S1–S4). Never random window splits. Scalers, feature selection and hyper-parameter search live inside the training folds (nested). Empty-room takes are dealt to folds take by take.
7. **Synthetic data** is labelled SYNTHETIC everywhere and never mixed with real results.
8. **Frozen interfaces** (`Predictor.predict(X, rssi)` output dict, `pipeline/preprocess.py` used by both offline and live, Format 1/2/3 in `docs/CONTRACTS.md`): change only with a version bump (`PREPROC_VERSION`, `FEATURES_VERSION`) and a note in `docs/decisions/DECISIONS.md`.
9. Work in phases; stop at each gate listed in the prompt and wait for the user's "go".
10. Install Python packages only inside the venv. No `sudo` without asking. Pin new packages in `host/requirements.txt` (or `requirements.txt` at the repo root, one file only).

## After every phase
Update `docs/STATUS.md` (replace the whole file): date/time, phase, what was done, verified results (with log paths), open problems, next step. Commit code and docs on a branch named `cc/<phase>`; never commit to `main` directly.
