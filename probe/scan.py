"""Brute-force scan of report-id / command byte for a vendor HID interface.

python scan.py VGN 0xFD cmd 0 255
python scan.py AULA 0x08 cmd 0 255
python scan.py K98 0x00 cmd 0 255
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hid_win

DEVICES = {
    "AULA": (0x249A, 0x5C2F, 0xFF01, 0x0010),
    "K98": (0x3554, 0xFA09, 0xFF02, 0x0002),
    "K98F": (0x3554, 0xFA09, 0xFF04, 0x0002),
    "VGN": (0x372E, 0x10BB, 0x000C, 0x0001),
}

key = sys.argv[1].upper()
rid = int(sys.argv[2], 0)
lo = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0
hi = int(sys.argv[4], 0) if len(sys.argv) > 4 else 255
gap = float(sys.argv[5]) if len(sys.argv) > 5 else 0.12

vid, pid, page, usage = DEVICES[key]
cands = [d for d in hid_win.find(vid, pid, page, usage) if not (d.usage_page == 0x000C and d.in_len == 3)]
dev = cands[0]
print("# %s %s out=%d in=%d" % (key, dev.vidpid, dev.out_len, dev.in_len))

h = hid_win.HidDevice(dev)
outlen = dev.out_len or 33
hits = 0
try:
    h.drain_input(30)
    for cmd in range(lo, hi + 1):
        buf = bytearray(outlen)
        buf[0] = rid
        buf[1] = cmd
        ok = h.write_output(bytes(buf))
        end = time.time() + gap
        while time.time() < end:
            r = h.read_input(30)
            if r:
                hits += 1
                print("  cmd=%02X write=%s  IN %s" % (cmd, ok, " ".join("%02X" % b for b in r)))
finally:
    h.close()
print("done, %d responses" % hits)
