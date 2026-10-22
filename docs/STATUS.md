# STATUS — 2026-10-22 14:45 IST · Phase 0 (set-up and audit) · waiting at Gate 0

## Done
1. The handover (`claude_code_handover.zip`, identical to `~/WiFi_CSI_Final/claude_code_handover/`) was copied to `docs/context/`. `~/WiFi_CSI_Final/CLAUDE.md` was already present and identical.
2. `git status`: the tree was clean on `main` (HEAD `e765966 before claude code`, 1 commit ahead of `origin/main`, not pushed). Nothing was uncommitted, so no `cc/baseline` branch was needed. Phase 0 work is committed on `cc/phase0`.
3. Read-only data audit: **125 takes: S1 37, S2 25, S3 22, S4 37, none 4**, as expected. All have both RX with CSI > 0, and decoded counts equal the meta counts. Details and anomalies are in `docs/AUDIT.md` §1.
4. Tree map and proposals: below.
5. `docs/AUDIT.md` written. The existing synthetic checks pass; there is no unit-test suite.

## Verified results (logs)
- `results/audit/raw_audit.log`, `results/audit/raw_takes.csv`: dataset counts and per-take link stats
- `results/audit/synthetic_tests.log`: T1–T5, SYNTHETIC
- `results/audit/v1_dryrun_real.log`: the v1 gate rejects 383 of 1377 real windows (27.8 %)

(`*.log` is git-ignored, so the logs stay on this laptop only.)

## Tree of `~/WiFi_CSI_Final` (sizes)
```
~/WiFi_CSI_Final                       5.3 G
├── CLAUDE.md                          4 K
├── claude_code_handover/              40 K   duplicate of the zip, now also in docs/context/
├── esp/esp-idf-v5.5.5/                4.2 G  toolchain (export.sh broken; keep)
├── hostenv/                           726 M  Python 3.12.3 venv (keep)
└── wifi-csi-har/                      398 M  git repo
    ├── data/raw/                      389 M  125 takes + _rejected/ (51) — READ-ONLY
    ├── data/processed/                empty
    ├── releases/v2/                   4.9 M  6 firmware images (committed to git)
    ├── docs/ 136 K · host/ 128 K (incl. __pycache__ 31 K) · firmware/ 100 K · tools/ 52 K
    ├── protocol/ 28 K · app/ 24 K · ml/ 24 K · pipeline/ 20 K · scripts/ 16 K · results/ 36 K
    └── .git/                          3.9 M
```
Outside the folder (not touched, listed for completeness): `~/csi_runs/{e0_first,e0_second,e0_v2,e0_swap,lib_empty,lib_person}` (bench runs); `~/Downloads/*.zip` (6 zips incl. two old repo snapshots) and the unpacked `~/Downloads/wifi-csi-har_2026-10-21_v2`.

The folder is already lean. There are no `data_synth`, `models_synth`, `build/` or stray scripts inside it.

## Proposed target structure (applied in Phase 6, after your approval)
```
wifi-csi-har/
  requirements.txt          single pinned file (moved from host/requirements.txt)
  host/                     csiwire, rx_check, record_session, csi_inspect
  pipeline/                 preprocess (shared), labelling, build_dataset, build_features
  ml/                       features, models/ (one file per track), train, evaluate, predict
  app/                      engine, dashboard
  firmware/{tx,rx}/ · tools/a0_antenna_check/ · releases/
  tests/                    pytest unit tests; tests/synthetic/ = generators moved from host/tests/
  scripts/                  pipeline.sh (or Makefile), audit_raw.py
  protocol/                 plan CSVs + take_overrides.csv (new, see D1)
  docs/  README-level: CONTRACTS, FEATURES, DECISIONS, STATUS, AUDIT, setup/, firmware/, context/, history/
  data/{raw (ro), processed, features} · models/ · results/ · logs/      (all git-ignored except metadata)
```

## Proposed moves (nothing moved yet)
| What | From | To | Why |
| --- | --- | --- | --- |
| `claude_code_handover/` | `~/WiFi_CSI_Final/` | `~/WiFi_CSI_Final/_archive/20261022/` | duplicate of `docs/context/` |
| `PROJECT_STATE.md`, `TEAM_PLAN.md`, `tracks/` | `wifi-csi-har/docs/` | `wifi-csi-har/docs/history/` (git mv, stays in repo) | superseded by PROJECT_CONTEXT + STATUS; kept as the project record |
| `host/tests/make_synthetic_*.py` | `host/tests/` | `tests/synthetic/` (git mv) | separate test fixtures from host tools |
| `host/requirements.txt` | `host/` | repo root (git mv) | one pinned file |
| `host/__pycache__/` | — | leave (git-ignored, regenerated) | no value in archiving |

Keep as they are: `protocol/plan_subject.csv` (used by the synthetic generator), `plan_s3_fix.csv` (provenance of S3 E50–E52), `tools/a0_antenna_check` (spare board still to test), `releases/v2` (depends on question 3 below), `esp/` and `hostenv/`.

## Open problems / questions for you at Gate 0
1. **D1 `S1_T29_walk` is `valid:false`** (passes D-017; probably the recorder was stopped at the prompt). Keep it via a `protocol/take_overrides.csv` override? I'd recommend yes. `meta.json` stays untouched either way.
2. **Decision-log path**: CLAUDE.md says `docs/decisions/DECISIONS.md`, PROMPT says `docs/DECISIONS.md`. Which one?
3. **`releases/v2/*.bin` are committed to git.** CLAUDE.md rule 4 literally forbids committing `.bin`. Keep them tracked (they are firmware, not data), or untrack them and keep SHA256SUMS?
4. Position/activity confound (D6) and the 27.8 % window rejection (P4) shape Phase 2–4; no action needed now, flagged for awareness.

## Next step
On "go": Phase 1, the firmware review (read and build only; nothing flashed). The ESP-IDF repair `./install.sh esp32,esp32s3` downloads toolchains, so I will ask before running it. Then the recorder bug fixes with simulated-port tests.
