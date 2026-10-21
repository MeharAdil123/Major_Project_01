# Track A: Hardware, recording, integration (owner: Mohith)

**Goal:** clean, labelled raw takes (Format 1) from the real boards, and the live demo hardware working at 14:00.

**Owns:** `firmware/`, `host/rx_check.py`, `host/record_session.py`, `host/csi_inspect.py`, `protocol/`, `docs/PROTOCOL.md`, `docs/setup/`. Also the GitHub repo (merges the other branches).
**Input:** the boards. **Output:** `data/raw/<session_id>/{RX1.bin,RX2.bin,meta.json}` (see CONTRACTS.md).

## Tonight
1. Repo on GitHub (`main` + branches `track-b`, `track-c`, `track-d`); add the 3 teammates as collaborators.
2. Real-data check: `python3 host/csi_inspect.py ~/csi_runs/e0_swap` → confirm the empty HT-LTF carriers match −58..−2, +2..+58 (the report prints `matches 802.11n HT40 layout`). If not, tell Sujal; `USED_SC` in `pipeline/preprocess.py` must change **before** tomorrow.
3. Dry run of the recorder with the boards: `python3 -m host.record_session --single walk --seconds 10 --subject TEST` → GOOD on both receivers. Delete the TEST folder after.
4. Pack: TX + power bank, 2 RX + cables, tape, chair, mat, mattress (if any), the object for bend_pick, a printed copy of PROTOCOL.md.

## Tomorrow
- 9:00–9:30 set-up and checks (PROTOCOL.md). 9:30–10:30 the takes. Copy `data/raw` to Sujal (USB stick or shared drive; **not** GitHub) after each subject.
- 10:30–12:00: extra takes if needed; then help Mehar (ML) with the results.
- 12:30–13:30: live demo rehearsal with Nihar on the real boards; keep the boards in the same layout.

## Done when
- ≥ 3 subjects recorded with ≥ 90 % takes GOOD, empty takes at the start, between subjects and at the end; layout photo committed.
- `scripts/pipeline.sh demo` shows the live state at about 2 updates/s on the real boards.

## Claude Code prompt (paste into Claude Code in the repo)
> Read docs/CONTRACTS.md, docs/PROTOCOL.md and host/record_session.py. I am running the recording tomorrow. Check the recorder for anything that could lose data during a take (port errors, disk full, a board resetting) and add handling without changing Format 1. Do not touch pipeline/, ml/ or app/.
