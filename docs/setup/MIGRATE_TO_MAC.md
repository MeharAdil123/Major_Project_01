# Moving the project to a MacBook (written 2026-10-22, end of Phase 3)

**What moves:** the repo (`~/WiFi_CSI_Final/wifi-csi-har`, including `.git`, `data/raw`, `data/features` and the untracked `results/**/*.log` evidence) and `~/WiFi_CSI_Final/CLAUDE.md`.
**What does not move:** `hostenv/` (Linux binaries; recreate it), `esp/` (Linux ESP-IDF; only needed for flashing), `data/processed` (2 GB; rebuild on the Mac so all Phase 4 results come from one machine).
**Rules that still apply:** copy, never move; the Linux laptop keeps its copy until the Mac copy is verified. **No cloud upload of recordings** (CLAUDE.md rule 4): use a USB drive or the local network, not iCloud, Google Drive or GitHub.

## Step A — the archive (already made on 2026-10-22, 20:18)
`~/WiFi_CSI_Final/transfer/wifi_csi_move.tar` (710 MB: `CLAUDE.md` + the whole repo except `data/processed` and `__pycache__`; it contains 534 raw `.bin` files) and its checksum file `wifi_csi_move.tar.sha256` (the hash changes whenever the archive is remade; always check against the .sha256 file made with it).
Remake it if the repo changed since then:
```bash
cd ~/WiFi_CSI_Final && tar --exclude='wifi-csi-har/data/processed' --exclude='__pycache__' -cf transfer/wifi_csi_move.tar CLAUDE.md wifi-csi-har && cd transfer && sha256sum wifi_csi_move.tar > wifi_csi_move.tar.sha256
```
Raw-data manifest inside the repo: `results/audit/raw_sha256.txt` (801 files incl. `_rejected`).

## Step B — move the archive (no USB drive, no cloud)
**Recommended: the Linux laptop makes its own Wi-Fi network and the Mac downloads from it.** Nothing goes through the internet (CLAUDE.md rule 4). The Linux Wi-Fi card supports access-point mode (checked: `WIFI-PROPERTIES.AP: yes`, 2.4 GHz). At ~20–50 Mbit/s, 710 MB takes about 3–6 minutes.
Why the earlier Wi-Fi attempt probably failed: the Linux firewall `ufw` is active and blocks incoming connections. Many networks (campus, phone hotspots) also block devices from reaching each other ("client isolation"). A direct hotspot avoids both once the port is opened.

While the hotspot is on, this laptop has **no internet**, so Claude Code here pauses. That is fine.

On the **Linux laptop** (Terminal):
1. Start a hotspot (pick your own password, at least 8 characters):
   ```bash
   nmcli device wifi hotspot ifname wlp2s0 ssid CSI-MOVE password 'choose-a-password'
   ```
   The laptop's address on this network is then `10.42.0.1` (check with `ip -4 addr show wlp2s0`).
2. Open one port in the firewall, only on the Wi-Fi interface:
   ```bash
   sudo ufw allow in on wlp2s0 to any port 8000 proto tcp
   ```
3. Serve the transfer folder (only the archive is in it):
   ```bash
   cd ~/WiFi_CSI_Final/transfer && python3 -m http.server 8000 --bind 10.42.0.1
   ```
   Leave this window open. It prints one line per download.

On the **MacBook**:
4. Wi-Fi menu → join **CSI-MOVE** with the password. (The Mac has no internet while joined; that is expected.)
5. Terminal (Applications → Utilities → Terminal):
   ```bash
   mkdir -p ~/Downloads/csi && cd ~/Downloads/csi
   curl -O http://10.42.0.1:8000/wifi_csi_move.tar
   curl -O http://10.42.0.1:8000/wifi_csi_move.tar.sha256
   shasum -a 256 -c wifi_csi_move.tar.sha256
   ```
   The last line must say `wifi_csi_move.tar: OK`. If not, delete the file and download again.
   (Browser alternative: open `http://10.42.0.1:8000/` in Safari and click the two files; then run the `shasum` line in `~/Downloads`.)

Back on the **Linux laptop**, undo everything:
6. Stop the server with `Ctrl+C`, then:
   ```bash
   sudo ufw delete allow in on wlp2s0 to any port 8000 proto tcp
   nmcli connection down Hotspot
   nmcli connection up Mohith
   ```
   (`Mohith` is the Wi-Fi this laptop used before; `nmcli connection show` lists the names.) Check with `sudo ufw status` that port 8000 is gone.

**If the hotspot does not start** (some Realtek drivers refuse): use one shared network instead, e.g. your phone hotspot `Mohith` with both laptops joined. Do steps 2–3 with the Linux address from `hostname -I` (today `10.25.158.247`) instead of `10.42.0.1`, and steps 4–5 with that address. If the Mac still cannot connect, the phone isolates clients; use the laptop hotspot or one of the options below.

**Other options without a pen drive:**
- **Ethernet cable:** the Linux laptop has a wired port (`enp1s0`). The Mac needs a USB-C-to-Ethernet adapter. Connect the cable, run `nmcli connection add type ethernet ifname enp1s0 con-name csi-wire ipv4.method shared` and `nmcli connection up csi-wire` on Linux (address `10.42.0.1` on the cable), then steps 2–6 with `enp1s0` instead of `wlp2s0`.
- **Android phone as the "drive":** connect the phone to the Linux laptop by USB (File transfer mode), copy the two files to the phone's Download folder, then connect the phone to the Mac and copy them off with OpenMTP or Android File Transfer. Check `shasum` as in step 5. (iPhones do not work this way with Linux.)
- **Not allowed:** iCloud, Google Drive, WhatsApp, e-mail, GitHub and other online services, for the recordings (CLAUDE.md rule 4).

## Step C — set up the MacBook
1. Command-line tools and Python 3.12:
   ```bash
   xcode-select --install
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   brew install python@3.12
   ```
2. Unpack (only after `shasum` said OK):
   ```bash
   mkdir -p ~/WiFi_CSI_Final && tar -C ~/WiFi_CSI_Final -xf ~/Downloads/csi/wifi_csi_move.tar
   ls ~/WiFi_CSI_Final            # CLAUDE.md  wifi-csi-har
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
