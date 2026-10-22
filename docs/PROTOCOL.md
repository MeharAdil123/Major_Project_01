# Recording protocol p1 (2026-10-22)

## Why these durations

- **States** (empty, sit, stand, walk, lie) are what the system recognises *while they last*. The classifier sees one 2-second window at a time. A 30 s take gives about 27 windows. Neighbouring windows are very similar, so a longer take adds little. What adds information is **more takes in different places, orientations and people**. Hence many short takes (30 s), not a few long ones.
- **Events** (fall, sit_down, stand_up, bend_pick) last 1–3 s. A 10 s take with a beep at 3 s gives still → movement → still. The movement is found automatically after the beep, so nobody has to mark times.
- The sitting-down *movement* (5–6 s at most) is the event `sit_down`. *Being seated* is the state `sit`. They are different classes.

## Budget

| Block | Takes | Recording | With changeovers |
| --- | --- | --- | --- |
| Empty baseline (B00) | 1 × 120 s | 2 min | 3 min |
| Per subject: 12 state takes + 12 event takes | 24 | 8 min | ≈ 14 min |
| Empty check between subjects (B01) | 1 × 30 s | 0.5 min | 1.5 min |
| 3 subjects | 72 | 24 min | ≈ 47 min |
| **Total** | ≈ 77 | ≈ 29 min | **≈ 55 min** |

Result per class: 9 takes per state (≈ 240 windows), 9 takes per event, empty ≈ 240 s. If time remains, run a second round with a 4th person or new positions. More people helps more than more takes from the same person.

## Room set-up (layout_A): draw it, photograph it, put the photo in `docs/setup/layout_A.jpg`

- TX (patch antenna) on one side of the room at about 1 m height, facing the open area. RX1 and RX2 (omnis vertical) on the other side or the adjacent wall at about 1 m, about 1.5–2 m apart. The person moves in the area between them.
- Mark with tape: chair spots **A, B, C** (different distances and angles), mat spot **L** (for lying), mattress spot **M** (for falls), and walking **path1** and **path2**.
  *Library recording, 22 Oct (corrected 2026-10-22 from the operator's sketch):* **path1 runs ALONG the link** (x ≈ −1.5, y 1.2→4.0) and **path2 runs ACROSS it** (y ≈ 2.55, x −2→+2); falls and lying were on mattress M (no separate mat L). The pre-recording plan here had them the other way round. Coordinates: `config/position_map.yaml`.
- Operator seat **O**: one fixed spot behind the receivers, outside the marked area. The operator sits still there during every take except empty ones. The laptop sits on a fixed table.
- Do not move furniture, boards, cables or the laptop once recording starts. If something moves, note it in `notes` and record a new empty take.
- The door stays in the same state (closed) for all takes.

## Before the first take (9:00–9:30)

1. Power the TX from the power bank. Check `power` and `status` once over USB if needed; record its power in `--tx-power`.
2. Run `python3 host/rx_check.py --seconds 20`. Both receivers must show at least 190 packets/s and RSSI between about −40 and −65 dBm with the subject standing in the middle. If RSSI is below −65, raise TX power (`power 10 save`) and re-check.
3. Run `scripts/pipeline.sh inspect` on a 20 s test take; check the heatmap reacts when someone walks.

## Running the takes

```bash
python3 -m host.record_session --plan protocol/plan_empty.csv --subject none --tx-power 5
python3 -m host.record_session --plan protocol/plan_subject.csv --subject P1 --tx-power 5
python3 -m host.record_session --plan protocol/plan_empty_short.csv --subject none --tx-power 5
python3 -m host.record_session --plan protocol/plan_subject.csv --subject P2 --tx-power 5
...
```
The recorder reads the instruction aloud (`spd-say`, if present), counts down, beeps at the cue, checks the take and asks keep/redo. `--from E05` resumes in the middle of a plan.

## Subjects

- Subject IDs P1, P2, P3 (no names in files). Write down height/build per ID on paper only if needed for the report.
- Ordinary clothes; no phones in pockets that might transmit Wi-Fi heavily (put phones on airplane mode or outside the room).
- Act naturally; between takes, change small things (how you sit, where you look). For walking, keep your normal speed.

## Fall safety (mandatory)

- Falls only onto a thick mattress or bed. If there is none, **skip E04, E08 and E12**; the fall detector is then not part of the demo.
- Fall from standing, sideways or backwards, knees first, protecting the head. No falls from a height, none onto hard floor.
- Anyone uncomfortable does not do falls. Stop at any pain.

## Quality rules

- A take is redone if the recorder says BAD (rate < 180/s or a gap > 100 ms), if the subject did the wrong thing, or if someone entered the room.
- The operator writes problems into the take's `meta.json` `notes`, or tells Track B to exclude it.
- At the end: one more empty take (B01) to check for drift over the morning.
