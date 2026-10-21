"""Decode CSI recordings made with host/rx_check.py --save (wire protocol v2).

A recording file (RX1.bin, RX2.bin) is the raw byte stream from one receiver:
    A5 5A | type u8 | len u16 LE | payload[len] | CRC-16/CCITT-FALSE LE over type..payload
Frame types: 0x01 HELLO (JSON), 0x02 STATS (JSON), 0x10 CSI (48-byte header + int8 CSI).

CSI layout (ESP-IDF v5.5.5 api-guides/wifi.rst, "Wi-Fi Channel State Information",
column: secondary channel below, HT, 40 MHz, non-STBC, total 384 bytes):
    bytes   0..127  L-LTF   64 values, sub-carrier index 0..63
    bytes 128..383  HT-LTF 128 values, sub-carrier index 0..63 then -64..-1
Each value is two int8: imaginary part first, then real part.
If FIRST_WORD_INVALID is set, the first 4 bytes (first 2 values) are invalid.

This module only decodes. It does not filter, normalise or interpret.
"""
from __future__ import annotations

import binascii
import json
import struct
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

SYNC = b"\xA5\x5A"
T_HELLO, T_STATS, T_CSI = 0x01, 0x02, 0x10
MAX_PAYLOAD = 2048

HDR = struct.Struct("<BBHIQQIIHbbbBBBBBBBHH")
assert HDR.size == 48
HDR_DTYPE = np.dtype([
    ("version", "u1"), ("rx_id", "u1"), ("flags", "<u2"), ("seq", "<u4"),
    ("tx_time_us", "<u8"), ("rx_time_us", "<u8"), ("rx_ctrl_ts", "<u4"), ("radio_id", "<u4"),
    ("mac_seq", "<u2"), ("rssi", "i1"), ("noise_floor", "i1"), ("tx_power_qdbm", "i1"),
    ("rate", "u1"), ("sig_mode", "u1"), ("mcs", "u1"), ("cwb", "u1"), ("channel", "u1"),
    ("secondary_channel", "u1"), ("reserved", "u1"), ("sig_len", "<u2"), ("csi_len", "<u2"),
])
assert HDR_DTYPE.itemsize == 48

F_SEQ_VALID = 1 << 0
F_RADIO_MISMATCH = 1 << 1
F_FIRST_WORD_INVALID = 1 << 2

# Layout for the only packet type our TX sends (HT40, secondary below, non-STBC).
CSI_LEN_HT40 = 384
N_LLTF = 64
N_HTLTF = 128
LLTF_INDEX = np.arange(0, 64)                                      # as documented: 0..63
HTLTF_INDEX = np.concatenate([np.arange(0, 64), np.arange(-64, 0)])  # buffer order
HTLTF_SC = np.arange(-64, 64)                                      # after reordering
HTLTF_ORDER = np.argsort(HTLTF_INDEX)                              # buffer -> -64..63

# 802.11n 40 MHz reference (IEEE 802.11-2020, 19.3.7): data+pilot sub-carriers
# -58..-2 and +2..+58, pilots at +-11, +-25, +-53. The ESP-IDF table text says
# -57..+57 / 114 total; csi_inspect.py measures which carriers are really empty.
HT40_PILOTS = np.array([-53, -25, -11, 11, 25, 53])
HT40_EXPECTED_USED = np.concatenate([np.arange(-58, -1), np.arange(2, 59)])


def crc16(body: bytes) -> int:
    """CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF), same as the firmware."""
    return binascii.crc_hqx(body, 0xFFFF)


@dataclass
class Recording:
    name: str
    hdr: np.ndarray                    # structured array, HDR_DTYPE, one row per CSI record
    csi_raw: np.ndarray                # int8 (N, 384); rows only for csi_len == 384
    hello: list = field(default_factory=list)
    stats: list = field(default_factory=list)
    crc_errors: int = 0
    bytes_total: int = 0
    other_len: dict = field(default_factory=dict)   # csi_len -> count of records not decoded

    @property
    def n(self) -> int:
        return len(self.hdr)


def iter_frames(data: bytes):
    """Yield (type, payload) for every CRC-valid frame; count CRC failures."""
    i, n = 0, len(data)
    errors = 0
    while True:
        j = data.find(SYNC, i)
        if j < 0 or j + 5 > n:
            break
        ftype = data[j + 2]
        ln = data[j + 3] | (data[j + 4] << 8)
        if ln > MAX_PAYLOAD:
            i = j + 1
            continue
        end = j + 7 + ln
        if end > n:
            break
        crc = data[end - 2] | (data[end - 1] << 8)
        if crc != crc16(data[j + 2: j + 5 + ln]):
            errors += 1
            i = j + 1
            continue
        yield ftype, data[j + 5: j + 5 + ln]
        i = end
    iter_frames.last_errors = errors


def load(path: str | Path, name: str | None = None) -> Recording:
    path = Path(path)
    data = path.read_bytes()
    hdrs, csis, hello, stats, other = [], [], [], [], {}
    for ftype, p in iter_frames(data):
        if ftype == T_CSI and len(p) >= HDR.size:
            csi_len = p[46] | (p[47] << 8)
            if len(p) != HDR.size + csi_len:
                continue
            if csi_len != CSI_LEN_HT40:
                other[csi_len] = other.get(csi_len, 0) + 1
                continue
            hdrs.append(p[:HDR.size])
            csis.append(p[HDR.size:])
        elif ftype == T_HELLO:
            try:
                hello.append(json.loads(p))
            except ValueError:
                pass
        elif ftype == T_STATS:
            try:
                stats.append(json.loads(p))
            except ValueError:
                pass
    hdr = np.frombuffer(b"".join(hdrs), dtype=HDR_DTYPE) if hdrs else np.zeros(0, HDR_DTYPE)
    csi = (np.frombuffer(b"".join(csis), dtype=np.int8).reshape(-1, CSI_LEN_HT40)
           if csis else np.zeros((0, CSI_LEN_HT40), np.int8))
    return Recording(name or path.stem, hdr, csi, hello, stats,
                     getattr(iter_frames, "last_errors", 0), len(data), other)


def to_complex(csi_raw: np.ndarray, hdr: np.ndarray | None = None):
    """int8 (N, 384) -> (lltf complex64 (N, 64), htltf complex64 (N, 128) ordered -64..63).

    Values flagged invalid by FIRST_WORD_INVALID become NaN.
    """
    v = csi_raw.astype(np.float32)
    z = (v[:, 1::2] + 1j * v[:, 0::2]).astype(np.complex64)   # imag first, then real
    if hdr is not None and len(hdr):
        bad = (hdr["flags"] & F_FIRST_WORD_INVALID) != 0
        z[bad, :2] = np.nan
    lltf = z[:, :N_LLTF]
    ht = z[:, N_LLTF:N_LLTF + N_HTLTF][:, HTLTF_ORDER]
    return lltf, ht


def tx_segments(seq: np.ndarray) -> list[slice]:
    """Split records where the TX rebooted (sequence number jumps back by > 1000)."""
    cut = np.flatnonzero(np.diff(seq.astype(np.int64)) < -1000) + 1
    edges = np.concatenate([[0], cut, [len(seq)]])
    return [slice(int(a), int(b)) for a, b in zip(edges[:-1], edges[1:]) if b > a]


class StreamDecoder:
    """Incremental frame decoder for live serial data (same rules as iter_frames)."""

    def __init__(self):
        self.buf = bytearray()
        self.crc_errors = 0

    def feed(self, data: bytes):
        self.buf += data
        out = []
        while True:
            i = self.buf.find(SYNC)
            if i < 0:
                del self.buf[: max(0, len(self.buf) - 1)]
                return out
            del self.buf[:i]
            if len(self.buf) < 5:
                return out
            ftype = self.buf[2]
            ln = self.buf[3] | (self.buf[4] << 8)
            if ln > MAX_PAYLOAD:
                del self.buf[:1]
                continue
            if len(self.buf) < 7 + ln:
                return out
            crc = self.buf[5 + ln] | (self.buf[6 + ln] << 8)
            if crc != crc16(bytes(self.buf[2:5 + ln])):
                self.crc_errors += 1
                del self.buf[:1]
                continue
            out.append((ftype, bytes(self.buf[5:5 + ln])))
            del self.buf[:7 + ln]


def parse_csi(payload: bytes):
    """One CSI frame payload -> (header record, int8 csi[384]) or None if not HT40/384."""
    if len(payload) < HDR.size:
        return None
    h = np.frombuffer(payload[:HDR.size], dtype=HDR_DTYPE)[0]
    if int(h["csi_len"]) != CSI_LEN_HT40 or len(payload) != HDR.size + CSI_LEN_HT40:
        return None
    return h, np.frombuffer(payload[HDR.size:], dtype=np.int8)
