# STATUS — 2026-10-23 · v1.0 · project complete

## State
All phases are done. The repository is self-contained: the project rules are in `docs/PROJECT_RULES.md`, and there are no assistant-specific files (D-061).

| Phase | Outcome | Evidence |
| --- | --- | --- |
| 0–1 | audit, firmware review, recorder fixes, Gate 0 decisions | `docs/AUDIT.md`, `docs/firmware/REVIEW_phase1.md`, D-018…D-033 |
| 2–3 | signal inspection, preprocessing v2, onset detector o2, dataset 2/3/4 s | `docs/analysis/`, `results/dataset/` |
| 4 | LOSO comparison of 3 tracks, final models (D-050), calibrated fall alarm (D-051) | `results/REPORT.md` §1–8, `results/phase4/` |
| 5 | live engine and dashboard, live = offline (bit-identical), environment check, library live tests, RX2 connector fault found and fixed | `results/REPORT.md` §9–10, `results/phase5/live_library/TEST_CONDITIONS.md` |
| 6 | archive, README, final report, reproduction, assistant-independent docs | README, D-061, D-062, `results/reproduction/` |

## Verified results
- LOSO (4 s, dynamic f2):
  - presence 0.698 ± 0.065;
  - state 0.572 ± 0.115;
  - events 0.539 ± 0.054;
  - fall alarm 21/42 falls with 8/109 look-alike alarms.
- Live test (2026-10-23, `results/phase5/live_library/live_steps_final.log`):
  - the system ran 14 min at 0.50 s steps;
  - walk across the link was recognised 37/42;
  - the fall gave no alarm;
  - walking gave 2 false fall alarms;
  - the empty room was partly called occupied.
- Reproduction from raw data (`scripts/pipeline.sh reproduce`, 11 min; `results/reproduction/`): all 801 raw files match their checksums; rebuilt 4 s features identical; retrained models identical on all 2401 windows; live = offline identical; tests pass.
- Unit tests: 93 passed.

## Open problems (future work, see `results/REPORT.md` §11)
- Presence model fragile on empty rooms; a still person can look empty. A per-site calibration is proposed (`docs/analysis/calibration_proposal.md`), not built.
- Fall detection catches about half of simulated falls (LOSO), all recorded at one spot.
- A connector/antenna health check is needed in the preflight (the RX2 U.FL fault, D-060).
- One room, one layout, 6 volunteers, no video ground truth.

## Housekeeping
- Remove the BSSID lock AC:DE:01:59:B1:41 from the RNSIT-STUDENTS connection and unblock Bluetooth (the team does this after the library session).
- `models/env_baseline.json` and other model files stay local (rule 4).
