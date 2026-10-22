"""Decoder round trip on SYNTHETIC frames."""
import json

import numpy as np

from host import csiwire as cw
from host.tests.make_synthetic_dataset import frame


def _csi_frame(seq, iq, flags=cw.F_SEQ_VALID, csi_len=384, rx_id=1):
    hdr = cw.HDR.pack(2, rx_id, flags, seq, 1000 + seq, 2000 + seq, seq, 0xCBD36978, seq & 0xFFF,
                      -40, -92, 20, 0, 1, 0, 1, 11, 2, 0, 32, csi_len)
    return frame(cw.T_CSI, hdr + iq.tobytes())


def test_roundtrip_and_reorder(tmp_path):
    # imag-first int8 pairs; HT-LTF buffer order 0..63 then -64..-1
    sc = np.arange(-64, 64)
    ht_true = (sc % 50 + 1) + 1j * (-(sc % 30))           # distinct value per sub-carrier
    lt_true = np.arange(64) + 1j * (np.arange(64) % 7)
    ht_buf = np.concatenate([ht_true[64:], ht_true[:64]])
    z = np.concatenate([lt_true, ht_buf])
    iq = np.empty(384, np.int8)
    iq[0::2] = z.imag.astype(np.int8)
    iq[1::2] = z.real.astype(np.int8)
    data = frame(cw.T_HELLO, json.dumps({"role": "rx"}).encode())
    data += b"\x00garbage\xA5"                               # junk between frames
    data += _csi_frame(7, iq) + _csi_frame(8, iq)
    bad = bytearray(_csi_frame(9, iq)); bad[60] ^= 0xFF      # corrupt payload -> CRC reject
    data += bytes(bad) + _csi_frame(10, np.zeros(256, np.int8), csi_len=256)
    f = tmp_path / "RX1.bin"; f.write_bytes(data)

    rec = cw.load(f)
    assert rec.n == 2 and list(rec.hdr["seq"]) == [7, 8]
    assert rec.crc_errors == 1
    assert rec.other_len == {256: 1}
    assert rec.hello == [{"role": "rx"}]
    lt, ht = cw.to_complex(rec.csi_raw)
    np.testing.assert_array_equal(ht[0], ht_true.astype(np.complex64))
    np.testing.assert_array_equal(lt[0], lt_true.astype(np.complex64))


def test_stream_decoder_matches_file_decoder(tmp_path):
    iq = np.arange(384, dtype=np.int64).astype(np.int8)
    data = b"".join(_csi_frame(s, iq) for s in range(20))
    dec = cw.StreamDecoder()
    got = []
    for i in range(0, len(data), 37):                        # arbitrary chunking
        got += [cw.parse_csi(p)[0]["seq"] for t, p in dec.feed(data[i:i + 37]) if t == cw.T_CSI]
    assert got == list(range(20))


def test_tx_segments_split_on_reboot():
    seq = np.array([100, 101, 102, 5000, 5001, 0, 1, 2, 3])
    segs = cw.tx_segments(seq)
    assert [(s.start, s.stop) for s in segs] == [(0, 5), (5, 9)]
