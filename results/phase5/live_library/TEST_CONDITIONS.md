# Live board test — library, 2026-10-23 09:18 IST

- Place: library hall, recording layout of 22 Oct (config/position_map.yaml v2, docs/setup/layout_library_sketch.jpg). Operator at the recording spot (user report).
- Firmware: v2 on all boards (v2.1 not flashed). TX standalone on its wall adapter; the TX serial port is not opened.
- Receivers on this laptop: RX1 /dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_28:84:85:85:5E:2C-if00, RX2 /dev/serial/by-id/usb-1a86_USB_Single_Serial_5C38144809-if00 (2 Mbaud).
- **Deliberate exception to D-032 (user, Gate 5):** laptop Wi-Fi stays connected so the development laptop keeps its network connection. Phones in airplane mode (user report).
- Checked before the preflight:
  - laptop Wi-Fi was connected to RNSIT-STUDENTS on **channel 11 (2462 MHz) = the CSI channel**;
  - other APs on channel 11 nearby (Rnsit_Library_staff, BLACKBERRY, Mini Audi);
  - **Bluetooth was not blocked** (rfkill).
  - Recommended to the user: move the laptop to an AP on channel 1 (RNSITLIBRARY ch 1, 2412 MHz, outside the 2432–2472 MHz span of the HT40 link) and switch Bluetooth off.
- 09:23 user: laptop locked to RNSIT-STUDENTS AP **BSSID AC:DE:01:59:B1:41, channel 1** (user-verified); Bluetooth blocked; tape clear, everyone outside and still. **To undo after the session:** remove the BSSID lock from the RNSIT-STUDENTS connection and unblock Bluetooth if wanted.

## Preflight 1 (09:24, `preflight.log`, raw streams in data/live_library/preflight_092334, not committed) — FAILED the agreed limits
- RX1: RSSI -36.1 dBm (baseline -36) OK; loss 4.3 %; 191.6 packets/s.
- RX2: RSSI **-33.3 dBm (baseline -38, +4.7 dB: outside ±3 dB)**; loss **10.0 %** (bursts of 27–37 % in single seconds); **79 UART CRC errors (2.2 %; 0 on every 22 Oct take; D-011 limit 0.5 %)**; 180 packets/s.
- Seen by both 87.2 %. HT40 100 %, TX power 5 dBm, no radio_id mismatch, no board/link queue drops.
- Interpretation: RX2 is ~5 dB stronger than when the data was recorded → its position, height (0.5 m) or antenna orientation probably differ from 22 Oct. The CRC errors are on the RX2 UART/USB link (cable, port or hub), not radio.
- Action: stop; check RX2 placement and cable; repeat the preflight.

## Preflight 2 (09:27, `preflight2.log`, raw streams data/live_library/preflight_092637) — FAILED the agreed limits
- Changes before it (user): the message kept the template text, so the actual changes are **not specified**. The RX2 serial device re-enumerated at 09:25 (replug seen).
- RX1: RSSI -36.0 dBm OK; loss **11.5 %** (radio side; 0 CRC errors).
- RX2: RSSI -33.6 dBm (unchanged; 22 Oct empty-room takes ranged -34 … -40, median -38); loss **12.5 %**; **108 UART CRC errors (3.0 %)**.
- Seen by both 81.5 %.
- Context checked: laptop load average 1.45 (not overloaded). Co-channel networks on ch 11 at this spot: RNSIT-STUDENTS B0:7C:51:55:74:B1 (signal 90) and B0:7C:51:45:A7:E1 (72), Rnsit_Library_staff (52), BLACKBERRY hotspot (45); rnsis-school on ch 10 (47).
- Interpretation: the higher loss on both receivers is in the air (co-channel library traffic at this time of day; cannot be fixed from our side without changing the channel, which would invalidate the models). The RX2 CRC errors remain unexplained (cable or USB port; 0 on 22 Oct).
- User (09:29): changes before preflight 2 were "reseated RX2 cable to the other laptop port; antenna height checked at 0.5 m".

## Decision (09:29, user)
Proceed under the recorded conditions: channel-11 library APs, ~12 % radio loss on both RX, RX2 CRC ~3 %, RX2 RSSI ~4.5 dB above the 22 Oct median. **This is a functional end-to-end test, not an accuracy measurement**; the LOSO results remain the evaluation. Preflight 3 is recorded only (non-blocking). Windows rejected or degraded are reported next to the predictions.
- Preflight 3 (09:30, record only, `preflight3.log`): RX1 RSSI -36.0, loss 8.4 %, 1 CRC error; RX2 RSSI -33.0, loss 14.5 %, 133 CRC errors (3.75 %); seen by both 82.1 %.

## b. Empty-room environment check (live, 60 s, log `live_20261023_093046.jsonl`)
- Verdict **"environment differs: predictions unreliable"**: 50 % of dynamic features outside the training empty 5–95 % range (median |z| 0.87, limit 2). Most shifted: rx2_diff_mean, rx2_sd_mean, rx1_rssi_std, rx2_sd_median, rx2_dph_w, i.e. RX2's temporal variation is higher than in the 22 Oct empty rooms.
- Presence model: occupied 0 % of check windows (dashboard: Empty, P(occupied) 0.08); fall threshold crossed 0 %.
- Static profile vs nearest training empty take (B01_empty_r4): 3.1 / 0.9 dB (training rooms differ by 3.2 dB among themselves).
- Gate: 41 of 129 steps so far "degraded" (window > 20 % missing); median live loss RX1 8.5 %, RX2 13.1 %.

## Restart (10:07, user: "redo the activity from the beginning")
Attempt 1 log kept as live_20261023_093046.jsonl (3355 lines, 13 markers). Fresh start: preflight 4 (record only) → new live session with the 60 s empty-room check → reconnect test → movements.
- Preflight 4 (10:07, record only, `preflight4.log`): RX1 RSSI -37.1 (min -49), loss 5.8 %, 0 CRC; RX2 RSSI **-36.0** (min -42; now within ±3 dB of -38), loss **7.7 %**, **10 CRC errors (0.27 %, within D-011)**; seen by both 89.8 %. RX2 is now within the agreed limits.

## Dashboard sessions and the engine-process fix (D-057)
- Session 1 (09:30, `live_20261023_093046.jsonl`, 13 markers): attempt 1, superseded by the user's restart. Session 2 (10:07, `live_20261023_100753.jsonl`): steps every ~1.45 s (p90 2.27 s) instead of 0.5 s; 90 of 222 steps "degraded"; env check finished late (differs; occupied 33 %).
- Diagnosis: the same engine headless (no Streamlit) stepped exactly every 0.50 s (step 243 ms median; env check: differs, occupied 75 %, 34 % of dynamic features outside). → In the dashboard, Streamlit page reruns and the engine shared one Python process, and the engine was starved.
- Fix: `app/engine_proc.py` runs the engine as its own program (`python -m app.engine_proc`), talking to the dashboard over a local authenticated socket. The engine code is unchanged.

## Session 3 (10:18, `live_20261023_101819.jsonl`) — the live test proper
- Step interval median 0.50 s, p90 0.61 s; step compute 383 ms median.
- Live loss median RX1 2.3 %, RX2 2.7 % (much lower than in sessions 1–2, where the starved process also fell behind on the serial streams).
- b. Empty-room check: **"environment differs: predictions unreliable"**, because the presence model said "occupied" in 92 % of 26 empty-room windows. Dynamic features match training (median |z| 0.45, 12 % outside the 5–95 % range); static profile 1.2 / 1.7 dB from the nearest training empty take. Fall threshold never crossed.

## Session 3 results (functional test; analysis `analysis.log`, `presence_check.log`, script `scripts/phase5_live_analysis.py`)
- Engine: 1945 steps, interval median 0.50 s / p90 0.51 s; live loss 3–6 %; no crash.
- d. RX2 reconnect (done after the movements): unplug 10:31:53 → **degraded after 3 s** ("RX2: no packets for > 1 s"), never a prediction on stale packets; replug → packets 10:32:19 → **ok again 10:32:24** after the 4.5 s buffer refill. There was no "RX2 replugged" marker; the "other" marker at 10:32:33 came after the replug.
- e. Movements (per marked segment, ok steps):
  - **No fall alarm at any time**, including the fall on the mattress (max P(fall) 0.33 there; 0.66 in one window later, without an alarm).
  - **No false fall alarms.**
  - **Presence/state mostly wrong with a person present:** stand at A "empty" 93/105; walk path1 walk 18/87 (mean P(occupied) 0.63); walk path2 walk 3/83 (P(occupied) 0.09); sit_down at A sit 9/32.
  - Event labels mostly sit_down/stand_up regardless of the movement.
  - The marked empty segment was correct (P(occupied) 0.10).
- Environment check was run 5 times (user pressed the button 4 more times). **Only the first result was logged** (logging bug: later results not written). The last one showed "ok" on the dashboard (screenshot 02; static profile 0.9 / 1.9 dB).
- Interpretation: the live chain works end to end (acquisition, alignment, gate, models, alarm rule, reconnect, logging, environment check). **The live predictions in this session do not reproduce the LOSO performance.** The cause cannot be established from the live log, which by design holds no CSI/features. Candidates: changed room/geometry since 22 Oct (TX re-aim, receiver positions, library traffic), the weak presence model meeting a new day, or an unknown systematic difference. A bug in the live path is unlikely: live = offline was verified bit-identical on recorded takes (D-054). The LOSO results remain the evaluation.

## Diagnostic takes (10:40–10:50, recorder v1.1, `data/live_library/diag_takes/`, not data/raw, subject "DX"; analysis `diag_analysis.log`, `scripts/phase5_diag_analysis.py`)
Six takes (empty, stand A, walk path1, walk path2, sit_down A, fall M), all GOOD, 0 CRC errors, loss RX1 3.4–7.9 %, RX2 4.3–5.4 %.
- **Receivers not swapped:** RX1.bin has MAC 28:84:85:85:5E:2C (rx_id 1), RX2.bin has 28:84:85:48:D7:DC (rx_id 2), today as on 22 Oct.
- **Offline = live failure** (not a live-path issue): walk path2 "empty" in 52/52 windows (P(occupied) 0.00; 22 Oct LOSO 0.96 walk); stand A "empty" 42/52; walk path1 walk 34/53; fall: no alarm (max P(fall) 0.29; LOSO 0.55); empty 53/53 correct; sit_down A recognised in 8/8 action windows.
- **RX2 shifted, RX1 not:**
  - RX2 RSSI −34 dBm in every take regardless of activity (22 Oct: −37 … −39 by activity).
  - RX2 motion/variation features (rx2_sd_mean, rx2_motion_mean/max, rx2_ph_cvar_w, rx2_pc1_logpower) at the 0th–5th percentile of the 22 Oct windows of the same activity/position in all six takes, i.e. RX2 hardly responds to motion.
  - RX1 features 10th–75th percentile; RX1 RSSI unchanged.
  - Static amplitude profiles of both RX within the 22 Oct take-to-take spread.
- **Verdict: setup shift localised at RX2** (strong, motion-insensitive direct path: position, orientation or height of the RX2 antenna relative to 22 Oct, or its antenna/connector). Not a live-path issue (offline equally wrong); not model weakness alone (walk path2 was 0.96 in LOSO and is 0.00 today).

## Known issues from today
- **Env-check logging bug:** only the FIRST environment-check result per session is written to the live log (`_env_logged` flag in `app/engine.py`). In session 3 the check ran 5 times; results 2–5 were not logged; the last showed "ok" on the dashboard (screenshot 02). Fix: log every completed check.
- The live log holds no `motion` level or features (by design, no CSI); diagnosing needed separate takes.
- **Reminder (user): remove the BSSID lock AC:DE:01:59:B1:41 from the RNSIT-STUDENTS connection, and unblock Bluetooth if wanted.**

## Next: Option A (fix RX2, then retest) — planned, not done
1. Physical checks at RX2 (and RX1 for comparison):
   - position (+1.3, 4.5) vs the sketch / `config/position_map.yaml`;
   - antenna tip height 0.5 m; same metal chair as 22 Oct;
   - antenna firmly clicked on the U.FL connector, same 6 dBi omni as RX1, pointing vertically (not toward the TX);
   - nothing new within ~0.5 m;
   - mattress M at x −0.5…1.5, y 2.9…3.8.
2. Record with `host/record_session` into `data/live_library/diag_takes2/` (not data/raw): walk path2 30 s + empty 30 s.
3. Compare vs 22 Oct with `scripts/phase5_diag_analysis.py` (point DIAG at the new folder). Success: RX2 RSSI ≈ −37 … −39 dBm and varying with the person; RX2 motion/variation features inside the 5–95 % range of 22 Oct; walk path2 recognised.
4. If fixed: a short live re-run (dashboard live mode, empty check + a few movements with markers).
5. If RX2 is still motion-blind: **antenna swap test**: swap the RX1/RX2 antennas (or move RX2's antenna to a known-good one) and repeat step 2–3, to separate antenna/connector from board/position.

## Option A, round 1 (2026-10-23, takes 11:05 and 11:06)
- RX2 physical check (user, via the question form): **position correct per the sketch; antenna re-seated and/or re-aimed** (the form did not say which, or how it pointed before). Not reported: height, chair, objects nearby, mattress.
- Takes (`protocol/plan_diag_live2.csv`, recorder `--auto`, same flags as 22 Oct, subject DX; `diag2_record.log`; `data/live_library/diag_takes2/`, not data/raw): E01 walk path2 30 s, E02 empty 30 s; both GOOD, 0 CRC errors, loss 4.5–6.8 %.
- Comparison (`scripts/phase5_diag_analysis.py diag_takes2` → `diag2_analysis.log`, `diag2_summary.json`):
  - RX2 RSSI **−36 dBm walk / −35 dBm empty** (before: −34 in every take; 22 Oct walk path2 median −39 [−41…−37], empty −38 [−40…−34]). It now moves by 1 dB between the takes; RX1 −35 in both.
  - E02 empty: correct (empty 48/53, P(occupied) median 0.10); **all 15 key features of both RX at the 32nd–88th percentile** of 22 Oct empty (before, rx2_sd_mean was at the 0th).
  - E01 walk path2: stand 33 / empty 19 of 52, no walk (P(occupied) median 0.64; before 0.00). **Motion features of RX1 and RX2 are both at the 0th–7th percentile**, whereas in the first walk path2 take (D04) RX1 was at the 24th–47th.
- Check of the motion over time (`scripts/phase5_motion_timeline.py` → `diag2_motion_timeline.log`; mean per-carrier amplitude SD in 2 s blocks): E01 RX1 3.4–4.8, RX2 3.5–4.1. That is **at or below the empty takes** (E02 RX1 3.9–5.7 with one 13.0 spike, D01 4.2–5.5), and below D04 walk (RX1 4.9–6.7) and the 22 Oct walk S1_T06 (RX1 up to 8.8, RX2 up to 13.7).
- Reading: in E01 neither receiver saw a person walking, so **E01 cannot test RX2**. It does not show RX2 is still blind. Open question to the user: was the walk done on path 2 for the full 30 s?
- User (~11:10): E01 confirmed, the walk did not happen during the recording window (operator error). **E01 is void** (kept on disk, not used).

## Option A, round 2: walk retake E03 (11:13)
- **Path naming conflict (open):** the user said the walker would walk "path 1 (the horizontal line)", then confirmed **path 1 = horizontal, path 2 = vertical**. That is the opposite of `config/position_map.yaml` v2 (path1 vertical along the link at x −1.5, path2 horizontal at y 2.55), which records the user's own Gate 0 correction of 22 Oct. Config not changed; to settle against `docs/setup/layout_library_sketch.jpg`. The user chose to label the take **walk path1** (their naming) and compare it with the 22 Oct path1 takes and D03.
- E03 walk path1, horizontal line, 30 s; the user said "go" at "recording" (`diag2b_record.log`): GOOD, 0 CRC, loss 5.8 / 6.2 %.
- Comparison (`diag2_analysis.log`, rerun on all of diag_takes2):
  - Offline prediction: **walk 42 / empty 10 of 52** (P(occupied) median 0.95). D03 this morning: walk 34 / empty 19; 22 Oct LOSO walk@path1: 1.00. There was **one fall alarm at 21.5 s during walking** (max P(fall) 0.54; D03: none).
  - RX1 normal: RSSI −36 (22 Oct −37), features at the 17th–75th percentile.
  - RX2: RSSI −36 (22 Oct median −38 [−41…−35]; D03 −34). Features still **low**: motion_mean 0, sd_mean 3, sc_corr 5, motion_max 16, pc1_logpower 13, ph_cvar_w 12 (D03: 0, 0, 5, 5, 1, 0).
  - Motion over time (`diag2_motion_timeline.log`): RX1 5.6–13.6 (a clear walk, like D03 5.1–14.4); RX2 3.9–6.7 (D03 3.2–6.0; 22 Oct S1_T06 walk up to 13.7).
- **Verdict:** RX2 is a little more responsive than this morning and its RSSI is back within ±3 dB of 22 Oct. It is **still near motion-blind** while walking, with core motion features at the 0th–5th percentile of 22 Oct. Walking is recognised, through RX1. The user's condition for the live re-run ("both receivers show normal motion and walking is recognised") is **not met**, so **no live re-run**. Next per plan: the antenna swap test.

## Option A, round 3: antenna swap test (takes 11:22 and 11:23)
- Swap (user, guided): tape-marked antennas, **A = was on RX1, B = was on RX2**. Both RX unplugged; TX untouched. **B → RX1, A → RX2**, both clicked, vertical, tip 0.5 m; boards, chairs and positions unchanged; USB replugged (RX2 same port). Inspection while unplugged: **all connectors, sockets and cables looked fine** (user).
- Takes (`protocol/plan_diag_live3.csv`, `diag3_record.log`, `data/live_library/diag_takes3/`, not data/raw): F01 walk path1 (horizontal line, user's naming; user said "go" at "recording"), F02 empty. Both GOOD, 0 CRC, loss 1.7–5.5 %.
- Comparison (`scripts/phase5_diag_analysis.py diag_takes3` → `diag3_analysis.log`, `diag3_summary.json`; `diag3_motion_timeline.log`):
  - **F01 walk path1:** walk **47/52** (P(occupied) median 1.00; E03 42/52, D03 34/53). **RX2 now responds to motion:** motion_mean 37, motion_max 16, sd_mean 28, pc1_logpower 46, ph_cvar_w 29, sc_corr 14 (percentiles of 22 Oct; E03 had 0/16/3/13/12/5). Amplitude SD over time: RX2 5.0–14.1 (E03 3.9–6.7; 22 Oct S1_T06 4.2–13.7). RX1 (now antenna B) stays normal (36th–68th percentile; 6.4–13.1). No fall alarm.
  - RSSI: RX1 −39 walking / −33 empty (22 Oct walk −37 [−37…−36], empty −37 [−37…−36]); RX2 −42 / −38 (22 Oct walk −38 [−41…−35], empty −38 [−40…−34]). **Both now change with the person** (by 6 and 4 dB). RX2 empty matches 22 Oct exactly; **RX1 empty is +4 dB** above its 22 Oct range.
  - **F02 empty:** all 15 key features of both RX at the 28th–82nd percentile of 22 Oct empty, and the motion timeline is flat (4–5, like E02). **But presence says occupied: stand 38 / empty 14 of 52, P(occupied) median 0.89** (E02 before the swap: empty 48/53, 0.10). Not explained yet. Candidates: someone still inside the area, or the presence model (50 dynamic features) reacting to features outside the 15 shown here after the antenna change.
- **Verdict:** antenna B moved to RX1 did **not** make RX1 blind. So the RX2 problem was **not** a faulty antenna B. The swap (a fresh U.FL mating on both boards) restored RX2's motion response. The most likely cause is an imperfectly mated U.FL contact at RX2, or the antenna/board pairing; the re-seat in round 1 did not fix it fully. Walking is recognised with both receivers normal. **Open:** false "occupied" on the new empty take.
- User: during F02 someone may still have been inside or moving, so **F02 is doubtful**. An empty retake follows.

## Option A, round 4: empty retake F03 (11:26, 20 s countdown; `diag3b_record.log`)
- F03 empty: GOOD, 0 CRC, loss 4.0 / 1.7 %. RSSI **RX1 −36, RX2 −36** (22 Oct empty −37 / −38: both within range). 15 key features at the 34th–84th percentile of 22 Oct empty (`diag3_analysis.log`, rerun on all of diag_takes3). Amplitude SD over time: RX1 6.3–8.9 (F02 3.6–5.0, E02 3.9–5.7 with one spike), steady with no walking bursts; RX2 4.0–4.8.
- **Presence still wrong: stand 46, lie 4, sit 3 of 53; P(occupied) median 0.97.**
- Why (`scripts/phase5_presence_contrib.py` → `presence_contrib.log`, logistic-regression contributions coef·z per feature; intercept +9.06):
  - In the 22 Oct empty take B00 (logit −3.5) and in E02 (logit −2.2, before the swap) the sum of contributions is about −12.5. In F02/F03 it is −8.0 / −5.5, so the logit becomes +2.1 / +3.6.
  - **No single feature is outside the 22 Oct empty range** (F03 top-10 features at the 6th–77th percentile). Many noise-level features (rx2_diff_p90, rx2_dph_p90, rx2_sd_p90, rx1_sd_mean …) sit near the middle of the 22 Oct empty distribution instead of its quiet end, and together they cross the boundary.
  - E02 was "correct" partly **because the motion-blind RX2 made the room look extra quiet** (rx2_diff_p90 at the 5.7th, rx2_dph_p90 at the 3.1st percentile).
  - The model is fragile on empty rooms even in its own evaluation: LOSO occupied share on the 22 Oct empty takes was 0.00–0.42 per take, 0.17 overall (`presence_empty_loso.log`, from `results/phase4/track_a/presence/logreg__dynamic__4s.pred.csv`).
- **Verdict:** after the swap the hardware senses motion again on both RX. The empty room now falls on the "occupied" side of a presence boundary that already sat inside the 22 Oct empty distribution. That is the documented weakness of the presence model (LOSO macro-F1 0.70; "a still person can look like an empty room", and here the reverse) meeting a changed antenna/board pairing. It is not a sensing failure. The live re-run would most likely fail its empty-room check (presence "occupied" > 20 %).
- **Proposed next step:** swap the antennas **back to the 22 Oct pairing (A → RX1, B → RX2)**, firmly clicked. The swap showed both antennas are fine, so the original fault was most likely the mating at RX2. Then record walk path1 + empty again. If both RX respond to motion and the empty take is empty, do the live re-run.

## Path naming settled (user, final plan, ~11:33)
**path1 = vertical, path2 = horizontal, as in `config/position_map.yaml` v2.** So the takes recorded as "walk path1" on the horizontal line, **E03 and F01, were in fact walk path2**. Their comparison in rounds 2–3 was made against the 22 Oct path1 (vertical) windows. Their RX2 percentiles are therefore relative to the wrong reference; the RX2 conclusion below rests on G02, which is labelled correctly. The meta.json files were left as recorded.

## Option A, round 5: antennas back to the 22 Oct pairing (11:33–11:38)
- User: antenna **A → RX1, B → RX2** (22 Oct pairing), each U.FL clicked firmly and rotate-checked; RX2 antenna vertical, 0.5 m, on its marked spot.
- Takes (`protocol/plan_diag_live4.csv`, `diag4_record.log`, `diag4b_record.log`, `data/live_library/diag_takes4/`):
  - G01 empty: **two attempts rejected by the recorder** (RX1 −45/−47 dBm, RX2 −54/−41 dBm, loss 18–47 %). The motion timeline showed continuous walk-level variation on both RX (amplitude SD 7–16): people were moving near the receivers. Kept in `_rejected/`, not used.
  - **G02 walk path2 (horizontal), 11:36:** GOOD. **walk 51/53** (22 Oct LOSO 0.96). RSSI RX1 −36, RX2 −37 (22 Oct walk path2 −37 / −39). **RX2 motion features 72nd–97th percentile, RX1 45th–84th** (`diag4_analysis.log`). RX2 amplitude SD 5.0–8.9 (`diag4_motion_timeline.log`). One fall alarm during the walk (10.5 s, max P(fall) 0.72).
  - **G03 empty, 11:37:** GOOD. RSSI −37/−37 (22 Oct −37 / −38), all 15 key features at the 15th–95th percentile of 22 Oct empty. **Presence: empty 24 / occupied 28 of 52, P(occupied) median 0.68** (`presence_contrib_G03.log`: again no feature out of range).
- **RX2 diagnosis (final):** RX2's motion blindness was a **connector/mating fault at RX2's U.FL**. Evidence: RX2 RSSI +4 dB and motion features at the 0th–5th percentile in every take this morning, with RX1 normal; a re-seat helped partially; after a full swap and a firm swap-back, RX2 is fully normal (72nd–97th percentile while walking), with both antennas working on either board. The board, its position and the antennas themselves are not the cause.

## Final live test (11:40–11:53, `live_20261023_114052.jsonl`; analyses `analysis_final.log` (per marker segment), `live_steps_final.log` (per action interval, `scripts/phase5_live_steps.py`))
- Set-up: dashboard live mode (`streamlit run app/live_app.py -- --serial --log-dir results/phase5/live_library --env-check 60`), engine in its own process (D-057), one browser tab (an embedded browser pane on the laptop). The step cues were **spoken** (`spd-say`) and marked in the dashboard at each step. Same RF conditions as earlier today (laptop Wi-Fi on, locked to channel 1; Bluetooth blocked). **No screenshots were taken of this session** (user decision).
- Cue timing: the walk path2 "go" was issued at 11:49:42–44, but the speech command returned late (11:50:34), so the cue may have been heard a few seconds late. The fall "go" was spoken at 11:51:55, 14 s after the marker (11:51:41). The per-step analysis uses the spoken-cue times.
- **System:** 1658 steps, interval median 0.50 s / p90 0.54 s, no crash, both RX connected throughout. Loss RX1 2–8 %, RX2 3–4 %. Degraded windows (> 20 % missing) during walk path2 (10/52) and the event steps (8/20 each), from RX1 loss bursts.
- **Environment check:** 4 completed runs, all "environment differs: predictions unreliable", **only because of the presence model**: occupied 58 / 28 / 72 / 64 % (limit 20 %). The dynamic features match the training empty rooms closely (median |z| 0.29–0.37, 4 % outside the 5–95 % range; limits 2 and 30 %); fall crossings 0 %. `start_env_check` was called 11 times in the session (run numbers 1, 2, 3, 11 completed). The extra starts came from the dashboard button; they were not part of the scripted sequence, and their source is not recorded.
- **Per step** (raw window labels in the action interval; `live_steps_final.log`):

| step | windows ok | prediction | P(occupied) median | result |
|---|---|---|---|---|
| empty (final 30 s) | 52/52 | empty 35, stand 17 | 0.39 | 35/52 correct |
| stand at A | 50/50 | stand 24, walk 18, empty 8 | 0.98 | 24/50 correct |
| walk path1 (vertical) | 51/51 | **empty 40**, walk 6, stand 5 | 0.42 | **6/51 correct** |
| walk path2 (horizontal) | 42/52 | **walk 37**, stand 3, empty 2 | 1.00 | 37/42 correct; **2 false fall alarms** (11:50:01 P 0.57, 11:50:12 P 0.50) |
| sit_down at A (10 s) | 12/20 | state stand 7, walk 3, sit 2 | 1.00 | event sit_down in 0 windows |
| stand_up at A (10 s) | 11/19 | state sit 10, walk 1 | 1.00 | event stand_up in 1 window |
| fall on mattress M (10 s) | 12/20 | walk 7, stand 4, empty 1 | 0.90 | event fall in 2 windows; max P(fall) 0.28; **no alarm** |

## Final assessment of the live tests (2026-10-23)
**What worked**
- The live chain end to end: acquisition from both boards, alignment, the gate (degraded or no_signal instead of predictions on stale data), all four models, the alarm rule, logging (now with every environment-check run), markers, and the engine process stepping every 0.50 s for 14 minutes without a crash. RX2 unplug/replug recovery was shown in session 3.
- Walking across the link (path2) is recognised live (37/42) and offline (G02 51/53). The engine computes the same windows as the offline pipeline (D-054).
- The environment check did its job: it reported "predictions unreliable" whenever the presence model misjudged the empty room.

**What failed**
- **Fall detection:** the fall on the mattress gave **no alarm** (max P(fall) 0.28), and walking across the link gave **2 false fall alarms**. In session 3 the fall also gave no alarm.
- **Presence and still states:** the empty room was called occupied in 28–72 % of environment-check windows and in 17/52 windows of the final empty step. Standing at A was correct in only 24/50 windows.
- **Walk along the link (path1, vertical): mostly "empty"** (40/51), although walking along path1 had LOSO 1.00 on 22 Oct.
- **Events sit_down / stand_up** were not recognised live (0 and 1 windows).

**Why (as far as the evidence goes)**
1. Most of the morning's failure was the **RX2 U.FL connector fault** (diagnosed and fixed above).
2. After the fix, the **presence model** (logistic regression, LOSO macro-F1 0.70 ± 0.07) is the weak link. Its empty/occupied boundary lies inside the 22 Oct empty-room feature distribution (LOSO: 0–42 % of empty windows called occupied per take). A new day with all features in range still lands on the wrong side. Presence gates the state labels, so its errors propagate.
3. The live test ran under different RF conditions from the training day: the laptop Wi-Fi was on (D-032 exception), co-channel library APs were nearby, and RX1 loss bursts reached 8 %. There was one operator/subject, not one of S1–S6.
4. The live steps are short (10–30 s, one repetition each), so they are a functional demonstration, not an accuracy measurement.

**The evaluation remains the leave-one-subject-out results in `results/REPORT.md`.** The live test shows that the system runs end to end on real boards. It also shows that its accuracy does not carry over reliably to a new session without re-calibration. The calibration routine proposed in `docs/analysis/calibration_proposal.md` is the obvious next step (not done).
