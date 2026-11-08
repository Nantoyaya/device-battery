import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hid_win

dev = hid_win.find(0x249A, 0x5C2F, 0xFF01, 0x0010)[0]
h = hid_win.HidDevice(dev)
try:
    h.drain_input(80)
    for cmd in (0x18, 0x19, 0x1A, 0x1B, 0x1C, 0x20, 0x28, 0x30, 0x40):
        buf = bytearray(33)
        buf[0] = 0x08
        buf[1] = cmd
        h.write_output(bytes(buf))
        print("OUT 08 %02X" % cmd)
        t0 = time.time()
        end = t0 + 2.0
        while time.time() < end:
            r = h.read_input(100)
            if r:
                print("   IN (+%.2fs) %s" % (time.time() - t0, r.hex(" ")))
finally:
    h.close()
