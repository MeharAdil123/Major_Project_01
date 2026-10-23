#!/usr/bin/env bash
# Build csi_tx / csi_rx (RX1, RX2) with ESP-IDF v5.5.5 WITHOUT export.sh.
# export.sh fails only because riscv32-esp-elf-gdb (a debugger) is missing; the compilers are
# installed, so this script puts them on PATH directly. It never downloads, flashes or opens a port.
# The proper repair (downloads toolchains, needs internet): cd $IDF_PATH && ./install.sh esp32,esp32s3
#
#   scripts/fw_build.sh tx|rx1|rx2 OUTDIR      -> OUTDIR/{build,sdkconfig,build.log,*_FLASH_AT_0x0.bin}
set -euo pipefail
TARGET=${1:?tx|rx1|rx2}; OUT=$(realpath -m "${2:?outdir}")
REPO=${REPO:-$(cd "$(dirname "$0")/.." && pwd)}   # REPO=<tree> builds another source tree
export IDF_PATH=${IDF_PATH:-$HOME/WiFi_CSI_Final/esp/esp-idf-v5.5.5}
T=$HOME/.espressif/tools
export IDF_PYTHON_ENV_PATH=$HOME/.espressif/python_env/idf5.5_py3.12_env
export ESP_ROM_ELF_DIR=$T/esp-rom-elfs/20241011/
export PATH=$IDF_PYTHON_ENV_PATH/bin:$T/xtensa-esp-elf/esp-14.2.0_20260121/xtensa-esp-elf/bin:$T/riscv32-esp-elf/esp-14.2.0_20260121/riscv32-esp-elf/bin:$T/esp32ulp-elf/2.38_20240113/esp32ulp-elf/bin:$IDF_PATH/tools:$PATH
case $TARGET in
  tx)  PROJ=$REPO/firmware/tx; DEFS="$PROJ/sdkconfig.defaults"; CHIP=esp32 ;;
  rx1) PROJ=$REPO/firmware/rx; DEFS="$PROJ/sdkconfig.defaults;$PROJ/sdkconfig.rx1"; CHIP=esp32s3 ;;
  rx2) PROJ=$REPO/firmware/rx; DEFS="$PROJ/sdkconfig.defaults;$PROJ/sdkconfig.rx2"; CHIP=esp32s3 ;;
  *) echo "unknown target $TARGET"; exit 1 ;;
esac
mkdir -p "$OUT"
{
  echo "== fw_build $TARGET $(date -Is)"; echo "IDF $(cd $IDF_PATH && git describe --tags)"; xtensa-esp-elf-gcc --version | head -1
  idf.py -C "$PROJ" -B "$OUT/build" -D SDKCONFIG="$OUT/sdkconfig" -D SDKCONFIG_DEFAULTS="$DEFS" set-target $CHIP
  idf.py -C "$PROJ" -B "$OUT/build" -D SDKCONFIG="$OUT/sdkconfig" -D SDKCONFIG_DEFAULTS="$DEFS" build
  # one image to flash at 0x0 (bootloader + partition table + app), like releases/v2
  (cd "$OUT/build" && python -m esptool --chip $CHIP merge_bin -o "$OUT/${TARGET}_FLASH_AT_0x0.bin" @flash_args)
  sha256sum "$OUT/${TARGET}_FLASH_AT_0x0.bin" "$OUT/build/"*.bin
} 2>&1 | tee "$OUT/build.log"
