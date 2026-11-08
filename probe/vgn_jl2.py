"""VGN 周听 (Jieli dongle): try the JL_RCSP frame with the report id in byte 0."""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hid_win


def crc16_ccitt(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def build(report_id, seq, payload, ch=0x10, sub=0x02, frag=0, more=0, size=32):
    f = bytearray(size)
    f[0] = report_id
    f[1] = 0xFE
    f[2] = seq & 0xFF
    f[3] = ch
    f[4] = 0x00
    f[5] = sub
    f[6] = frag
    f[7] = more
    f[8] = len(payload) & 0xFF
    f[9] = (len(payload) >> 8) & 0xFF
    f[10:10 + len(payload)] = payload
    crc = crc16_ccitt(bytes(f[1:10 + len(payload)]))
    f[10 + len(payload)] = (crc >> 8) & 0xFF
    f[11 + len(payload)] = crc & 0xFF
    return bytes(f)


dev = [d for d in hid_win.find(0x372E, 0x10BB, 0x000C, 0x0001) if d.in_len == 32][0]
print("VGN out", dev.out_len, "in", dev.in_len)
h = hid_win.HidDevice(dev)
try:
    h.drain_input(50)
    seq = 0
    for rid in (0xFD, 0xFF):
        for ch in (0x10, 0x11):
            for tlv in (b"\x01\x00", b"\x01"):
                for sub in (0x02, 0x03):
                    buf = build(rid, seq, tlv, ch=ch, sub=sub)
                    seq = (seq + 1) & 0xFF
                    ok = h.write_output(buf)
                    print("OUT rid=%02X ch=%02X sub=%02X tlv=%s ok=%s  %s" % (
                        rid, ch, sub, tlv.hex(" "), ok, buf.hex(" ")))
                    got = []
                    end = time.time() + 0.5
                    while time.time() < end:
                        r = h.read_input(100)
                        if r:
                            got.append(r.hex(" "))
                    for g in got:
                        print("   IN  ", g)
finally:
    h.close()
