"""Vary byte[2] of an output report, fixed byte[0..1]."""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hid_win

DEVICES = {
    "AULA": (0x249A, 0x5C2F, 0xFF01, 0x0010),
    "K98": (0x3554, 0xFA09, 0xFF02, 0x0002),
    "VGN": (0x372E, 0x10BB, 0x000C, 0x0001),
}

key = sys.argv[1].upper()
rid = int(sys.argv[2], 0)
mid = int(sys.argv[3], 0)
lo = int(sys.argv[4], 0) if len(sys.argv) > 4 else 0
hi = int(sys.argv[5], 0) if len(sys.argv) > 5 else 255
gap = float(sys.argv[6]) if len(sys.argv) > 6 else 0.2

vid, pid, page, usage = DEVICES[key]
devs = [d for d in hid_win.find(vid, pid, page, usage) if not (d.usage_page == 0x000C and d.in_len == 3)]
dev = devs[0]
print("# %s %s out=%d in=%d" % (key, dev.vidpid, dev.out_len, dev.in_len))
h = hid_win.HidDevice(dev)
try:
    h.drain_input(50)
    for cmd in range(lo, hi + 1):
        buf = bytearray(dev.out_len)
        buf[0] = rid
        buf[1] = mid
        buf[2] = cmd
        ok = h.write_output(bytes(buf))
        got = []
        end = time.time() + gap
        while time.time() < end:
            r = h.read_input(40)
            if r:
                got.append(r.hex(" "))
        if got:
            print("byte2=%02X ok=%s | %s" % (cmd, ok, " || ".join(got)))
        sys.stdout.flush()
finally:
    h.close()
