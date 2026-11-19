"""Simulated receiver port for recorder/engine tests (SYNTHETIC frames in wire protocol v2)."""
import json
import threading
import time

import numpy as np

from host import csiwire as cw
from tests.synthetic.make_synthetic_dataset import frame

IQ = (np.arange(384) % 50 - 25).astype(np.int8)


class FakeSerial:
    """read() returns the frames 'sent' since the last call, at `rate` CSI packets/s + 1 STATS/s.

    mode: "normal" | "no_csi" (TX off: STATS only) | "die" (SerialException after die_after s)
          | "silent" (returns b"" after die_after s, like a USB link that stopped)
    """

    def __init__(self, rx_id=1, rate=200.0, mode="normal", die_after=0.4):
        self.rx_id, self.rate, self.mode, self.die_after = rx_id, rate, mode, die_after
        self.t0 = time.monotonic()
        self.sent_csi = 0
        self.sent_stats = 0
        self.closed = False
        self.lock = threading.Lock()

    def _csi(self, seq):
        hdr = cw.HDR.pack(2, self.rx_id, cw.F_SEQ_VALID, seq, seq * 5000, seq * 5000, seq, 0xCBD36978,
                          seq & 0xFFF, -40, -92, 20, 0, 1, 0, 1, 11, 2, 0, 32, 384)
        return frame(cw.T_CSI, hdr + IQ.tobytes())

    def read(self, n):
        time.sleep(0.005)
        el = time.monotonic() - self.t0
        if self.mode == "die" and el > self.die_after:
            import serial
            raise serial.SerialException("device reports readiness to read but returned no data")
        if self.mode == "silent" and el > self.die_after:
            return b""
        out = bytearray()
        with self.lock:
            while self.sent_stats < int(el) + 1:
                out += frame(cw.T_STATS, json.dumps({"type": "stats", "rx_id": self.rx_id}).encode())
                self.sent_stats += 1
            if self.mode != "no_csi":
                while self.sent_csi < int(el * self.rate):
                    out += self._csi(1000 + int(self.sent_csi * 200 / self.rate))
                    self.sent_csi += 1
        return bytes(out)

    def close(self):
        self.closed = True


def opener_for(spec: dict):
    """spec: {port_name: FakeSerial kwargs}. Unknown names get a normal port."""
    def opener(port, baud):
        kw = dict(spec.get(port, {}))
        return FakeSerial(rx_id=1 if "1" in port else 2, **kw)
    return opener
