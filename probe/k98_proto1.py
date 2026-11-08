import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hid_win


def frames_for(out_len):
    f1 = [0x08, 0x04] + [0x00] * 15 + [0x49]
    f2 = [0x08, 0x04] + [0x00] * 15 + [0x49] + [0x00] * 3
    return [f1, f2, [0x08, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x49]]


dev = [d for d in hid_win.find(0x3554, 0xFA09, 0xFF02, 0x0002)][0]
print("K98 out", dev.out_len, "in", dev.in_len)
h = hid_win.HidDevice(dev)
try:
    h.drain_input(50)
    for f in frames_for(dev.out_len):
        buf = bytearray(dev.out_len)
        buf[0:len(f)] = f
        ok = h.write_output(bytes(buf))
        print("OUT len=%d %s ok=%s" % (len(buf), bytes(buf).hex(" "), ok))
        end = time.time() + 0.6
        while time.time() < end:
            r = h.read_input(120)
            if r:
                print("   IN  %s" % r.hex(" "))
finally:
    h.close()
