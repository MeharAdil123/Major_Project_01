# Firmware builds — 2026-10-22 (Phase 1; nothing flashed)

Toolchain: ESP-IDF v5.5.5, xtensa-esp-elf-gcc esp-14.2.0_20260121 (14.2.0), cmake 3.28.3, ninja 1.11.1.
Command: `scripts/fw_build.sh <tx|rx1|rx2> <outdir>`. For the v2 rebuild, `REPO=<git archive of e765966>` was set. Build dirs are in the session scratchpad; the full logs (`*.log`, git-ignored) are next to this file.

| Image | Source | Warnings / errors | App size | Merged image SHA-256 | Equals `releases/v2`? |
| --- | --- | --- | --- | --- | --- |
| TX v2 rebuild | e765966 | 0 / 0 | 0xb9ea0 | f81b84fc95ffead2e44f18a14d80438de4b4d534b0ed947c0e1ade37c08b9154 | **yes, bit-identical** |
| RX1 v2 rebuild | e765966 | 0 / 0 | 0xbd990 | af0746a135fd1adf8151cdafd9d189afc261252c6dbd75a7ee0ad14a4c72e205 | **yes** |
| RX2 v2 rebuild | e765966 | 0 / 0 | 0xbde00 | 757708486c0072d2770fc51a7eeaa499b0f4d6434f35bc2a48e98efd1b86287d | **yes** |
| TX v2.1 | cc/phase1 | 0 / 0 | 0xba1f0 (27 % free) | 893dbf1583e4c3248543453244e8bc19da0dbcb2bbc82596064bd5951fd6cd27 | — (candidate) |
| RX1 v2.1 | cc/phase1 | 0 / 0 | 0xbdd40 (26 % free) | 31f518c16994058675c949d0fd6ae060edc59a8658a9bf3df6c92bf6efe0185f | — (candidate) |
| RX2 v2.1 | cc/phase1 | 0 / 0 | 0xbe1a0 (26 % free) | 90ebf7c2c3b0d0529f69e87038159288aabe8fc795fa10a1a75a8d4dce78de3e | — (candidate) |

v2.1 sdkconfig check (TX): `CONFIG_TX_POWER_QDBM=20`, `CONFIG_ESP_TASK_WDT_PANIC=y`.
The v2.1 images are **not** copied to `releases/`. They are added only if you approve flashing, after a bench test.
