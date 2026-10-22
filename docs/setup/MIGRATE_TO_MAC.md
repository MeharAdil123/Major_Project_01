# Moving the project to a MacBook (written 2026-10-22, end of Phase 3)

**What moves:** the repo (`~/WiFi_CSI_Final/wifi-csi-har`, including `.git`, `data/raw`, `data/features` and the untracked `results/**/*.log` evidence) and `~/WiFi_CSI_Final/CLAUDE.md`.
**What does not move:** `hostenv/` (Linux binaries; recreate it), `esp/` (Linux ESP-IDF; only needed for flashing), `data/processed` (2 GB; rebuild on the Mac so all Phase 4 results come from one machine).
**Rules that still apply:** copy, never move; the Linux laptop keeps its copy until the Mac copy is verified. **No cloud upload of recordings** (CLAUDE.md rule 4): use a USB drive or the local network, not iCloud, Google Drive or GitHub.

## On the Linux laptop
1. Everything is committed on `cc/phase3` / `cc/phase4`. Check: `git -C ~/WiFi_CSI_Final/wifi-csi-har status`.
2. Plug in a USB drive (exFAT, ≥ 2 GB free) and copy:
   ```bash
   tar -C ~/WiFi_CSI_Final --exclude='wifi-csi-har/data/processed' --exclude='__pycache__' -cf /media/$USER/<DRIVE>/wifi_csi_move.tar CLAUDE.md wifi-csi-har
   ```
   (Alternative over Wi-Fi: `rsync -a --exclude data/processed --exclude __pycache__ ~/WiFi_CSI_Final/wifi-csi-har <mac-user>@<mac-ip>:~/WiFi_CSI_Final/` after enabling Remote Login on the Mac.)
3. Raw-data checksum manifest (made 2026-10-22): `results/audit/raw_sha256.txt`, 801 files; its own SHA-256 is `949d2a3b3aa9e1b00e61ed0a470388883ae17af6e82dccf99cdd77721fbb84b6`.

## On the MacBook
1. Command-line tools and Python 3.12:
   ```bash
   xcode-select --install
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   brew install python@3.12
   ```
2. Unpack:
   ```bash
   mkdir -p ~/WiFi_CSI_Final && tar -C ~/WiFi_CSI_Final -xf /Volumes/<DRIVE>/wifi_csi_move.tar
   ```
3. Verify the raw data (every line must say OK):
   ```bash
   cd ~/WiFi_CSI_Final/wifi-csi-har/data/raw && shasum -a 256 -c ../../results/audit/raw_sha256.txt | grep -vc ": OK$"
   ```
   The printed count must be `0`.
4. Python environment (same path as on Linux):
   ```bash
   python3.12 -m venv ~/WiFi_CSI_Final/hostenv
   ~/WiFi_CSI_Final/hostenv/bin/pip install -r ~/WiFi_CSI_Final/wifi-csi-har/host/requirements.txt
   ```
   On macOS two pins differ: use `torch==2.14.1` (no `+cpu` suffix; the Mac wheel is the CPU/MPS build) and `xgboost==3.4.1` if `xgboost-cpu` has no Mac wheel. Record what was installed in `docs/decisions/DECISIONS.md`.
5. Check:
   ```bash
   cd ~/WiFi_CSI_Final/wifi-csi-har && ../hostenv/bin/python -m pytest
   ../hostenv/bin/python scripts/audit_raw.py --decode
   ```
   Expect all tests to pass and `expected counts (dataset_expected.yaml): MATCH` with 202 takes.
6. Install Claude Code, sign in with the same account, open `~/WiFi_CSI_Final`, and start with:
   > Read CLAUDE.md, docs/STATUS.md, docs/setup/MIGRATE_TO_MAC.md and docs/context/PROJECT_CONTEXT.md. We moved to a MacBook; verify the move, rebuild the 2/3/4 s datasets, then continue Phase 4 from STATUS.md and stop at Gate 4.

   The conversation itself does not carry over; the hand-over lives in `docs/STATUS.md`, `docs/decisions/DECISIONS.md` and the analysis docs.

## Things that stay on the Linux laptop for now
- **Boards** (flashing, recording, the live demo): the code finds ports through `/dev/serial/by-id`, which is Linux-only. On macOS the ports are `/dev/cu.usbmodem…` (RX1) and `/dev/cu.wchusbserial…` (RX2, CH343). Using them needs a small port-finding change in `host/record_session.py` and `app/engine.py` (Phase 5), plus a Mac ESP-IDF install for flashing.
- The udev rule (`setup/linux/`) is Linux-only.
- Keep the Linux copy of `data/raw` as the backup.
