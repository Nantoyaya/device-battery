import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hid_win

devs = hid_win.find(0x249A, 0x5C2F, 0xFF01, 0x0010)
print("found", len(devs))
dev = devs[0]
h = hid_win.HidDevice(dev)
try:
    h.drain_input(60)
    for cmd in (0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x1A, 0x20):
        buf = bytearray(33)
        buf[0] = 0x08
        buf[1] = cmd
        h.write_output(bytes(buf))
        t0 = time.time()
        while time.time() - t0 < 2.0:
            r = h.read_input(60)
            if r and len(r) > 1 and r[1] == cmd:
                print("cmd=%02X %s" % (cmd, r.hex(" ")))
                break
finally:
    h.close()
