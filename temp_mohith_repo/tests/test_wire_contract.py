"""Firmware <-> host contract: the C structs in csi_wire.h and the Python decoder must agree."""
import re
import zlib

import numpy as np

from host import csiwire as cw

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
C2NP = {"uint8_t": "u1", "int8_t": "i1", "uint16_t": "<u2", "uint32_t": "<u4", "uint64_t": "<u8"}


def c_struct(text, name):
    body = re.search(r"typedef struct __attribute__\(\(packed\)\) \{([^}]*)\}\s*" + name + ";", text, re.S).group(1)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    return [(m.group(2), C2NP[m.group(1)]) for m in re.finditer(r"(\w+_t)\s+(\w+);", body)]


def test_record_header_matches_decoder():
    h = (ROOT / "firmware/rx/main/csi_wire.h").read_text()
    fields = c_struct(h, "csi_rec_hdr_t")
    assert [(n, np.dtype(t)) for n, t in fields] == [(n, cw.HDR_DTYPE[n]) for n in cw.HDR_DTYPE.names]
    assert np.dtype(fields).itemsize == 48 == cw.HDR.size


def test_tx_payload_identical_in_tx_and_rx():
    rx = c_struct((ROOT / "firmware/rx/main/csi_wire.h").read_text(), "tx_payload_t")
    tx = c_struct((ROOT / "firmware/tx/main/main.c").read_text(), "tx_payload_t")
    assert rx == tx and np.dtype(rx).itemsize == 24


def test_flag_bits_match():
    h = (ROOT / "firmware/rx/main/csi_wire.h").read_text()
    bit = {m.group(1): int(m.group(2)) for m in re.finditer(r"#define CSI_F_(\w+)\s+\(1u << (\d+)\)", h)}
    assert 1 << bit["SEQ_VALID"] == cw.F_SEQ_VALID
    assert 1 << bit["RADIO_MISMATCH"] == cw.F_RADIO_MISMATCH
    assert 1 << bit["FIRST_WORD_INVALID"] == cw.F_FIRST_WORD_INVALID


def test_radio_id_of_the_study_settings():
    # esp_rom_crc32_le(0, s) == standard CRC-32 of the fingerprint used by TX and RX
    fp = b"ch=11;bw=HT40;rate=MCS0_LGI;hz=200;payload=32"
    assert zlib.crc32(fp) == 0xCBD36978
    for f in ("firmware/tx/main/main.c", "firmware/rx/main/main.c"):
        assert '"ch=%d;bw=%s;rate=MCS0_LGI;hz=%d;payload=%d"' in (ROOT / f).read_text()


def test_crc16_matches_firmware_algorithm():
    def fw_crc(p):                                   # transliteration of link.c crc16_ccitt
        crc = 0xFFFF
        for b in p:
            crc ^= b << 8
            for _ in range(8):
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
        return crc
    for p in (b"", b"123456789", bytes(range(256))):
        assert cw.crc16(p) == fw_crc(p)
    assert cw.crc16(b"123456789") == 0x29B1           # CRC-16/CCITT-FALSE check value
