"""Scan commands, waiting for the reply whose byte[1] echoes the command."""

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
lo = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0
hi = int(sys.argv[4], 0) if len(sys.argv) > 4 else 255
timeout = float(sys.argv[5]) if len(sys.argv) > 5 else 2.2

vid, pid, page, usage = DEVICES[key]
devs = [d for d in hid_win.find(vid, pid, page, usage) if not (d.usage_page == 0x000C and d.in_len == 3)]
dev = devs[0]
print("# %s %s out=%d in=%d" % (key, dev.vidpid, dev.out_len, dev.in_len))
h = hid_win.HidDevice(dev)
try:
    h.drain_input(80)
    for cmd in range(lo, hi + 1):
        buf = bytearray(dev.out_len)
        buf[0] = rid
        buf[1] = cmd
        h.write_output(bytes(buf))
        t0 = time.time()
        while time.time() - t0 < timeout:
            r = h.read_input(60)
            if not r:
                continue
            if len(r) > 1 and r[1] == cmd:
                print("cmd=%02X (+%.2fs) %s" % (cmd, time.time() - t0, r.hex(" ")))
                break
            print("cmd=%02X (+%.2fs) OTHER %s" % (cmd, time.time() - t0, r.hex(" ")))
        sys.stdout.flush()
finally:
    h.close()
