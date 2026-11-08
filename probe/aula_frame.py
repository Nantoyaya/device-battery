import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hid_win

dev = [d for d in hid_win.find(0x249A, 0x5C2F, 0xFF01, 0x0010)][0]
print("caps", dev.in_len, dev.out_len, dev.feat_len)
h = hid_win.HidDevice(dev)


def send(buf, gap=0.4, tag=""):
    buf = bytes(buf) + bytes(33 - len(buf))
    ok = h.write_output(buf)
    print("OUT %-24s %s  ok=%s" % (tag, buf.hex(" "), ok))
    end = time.time() + gap
    while time.time() < end:
        r = h.read_input(100)
        if r:
            print("   IN  %s" % r.hex(" "))


try:
    h.drain_input(50)
    send([0x10], tag="cmd@byte0=0x10")
    send([0x08, 0x10], tag="hdr08 cmd@1=0x10")
    send([0x00, 0x10], tag="hdr00 cmd@1=0x10")
    send([0x10, 0x08], tag="cmd@0=0x10 08")
    # maybe byte2 selects sub-register
    for cmd in (0x18, 0x19, 0x1A, 0x20, 0x21, 0x22, 0x30, 0x40, 0x50):
        send([0x08, cmd, 0x01], gap=0.5, tag="cmd=%02X sub=1" % cmd)
finally:
    h.close()
