# Proposal: short labelled calibration for a new room (NOT built; phase plan 5.4: "propose, do not build without asking")

**Why.** The models were trained in one room (library hall) with one layout. CSI depends on the room's multipath. In our own data the static channel shape already changed by 3.4 / 4.4 dB between two sessions in the same room (D-033), and published work reports accuracy collapsing when the room changes. The start-up environment check (`app/envcheck.py`) can tell that the room differs, but cannot fix it.

**What the operator would do (≈ 8 minutes, one volunteer, laptop Wi-Fi and Bluetooth off).** Use the existing recorder (`host/record_session.py`) with a new plan file `protocol/plan_calibration.csv`:

| Take | Duration | Purpose |
| --- | --- | --- |
| empty room ×2 | 60 s each | new empty-room baseline (environment check + presence) |
| stand still at 2 spots | 30 s each | still person ≠ empty room (the weakest case, REPORT §2) |
| sit still at 2 spots | 30 s each | same |
| walk across the space | 60 s | walking reference (walking false alarms) |
| sit_down ×3, stand_up ×3 | 10 s each, cue at 3 s | look-alike movements (false fall alarms) |
| (no falls) | — | simulated falls need the mattress and a spotter; not part of a quick calibration |

**What the software would do.**
1. Replace `models/env_baseline.json` with the new room's empty takes (environment check now relative to this room).
2. Re-fit only cheap, low-risk parts on the new takes plus the original training data, with the new room's takes given extra weight:
   - presence logistic regression (very few parameters; the main beneficiary);
   - the fall-alarm threshold θ, re-selected with the D-051 constraints on the calibration look-alikes and walking (θ only, rule kept).
3. Keep the state, event and fall models unchanged (too little calibration data to retrain them safely).
4. Report before/after on the calibration takes. These are in-sample for the re-fitted parts, so they show only that nothing broke. A held-out repeat of 2–3 takes recorded after calibration is the real check.

**Risks.** The calibration is very small (one person, minutes of data); over-fitting to the volunteer. There are no falls in the new room, so fall *sensitivity* stays unknown there; only false-alarm behaviour is calibrated.
