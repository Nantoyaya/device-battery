import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hid_win


def run(key, frames, vid, pid, page, usage, gap=0.5):
    devs = [d for d in hid_win.find(vid, pid, page, usage) if not (d.usage_page == 0x000C and d.in_len == 3)]
    dev = devs[0]
    print("==", key, dev.vidpid, "out", dev.out_len, "in", dev.in_len)
    h = hid_win.HidDevice(dev)
    try:
        h.drain_input(50)
        for f in frames:
            buf = bytearray(dev.out_len)
            buf[0:len(f)] = bytes(f)
            ok = h.write_output(bytes(buf))
            print("OUT %s ok=%s" % (bytes(buf).hex(" "), ok))
            end = time.time() + gap
            while time.time() < end:
                r = h.read_input(120)
                if r:
                    print("   IN  %s" % r.hex(" "))
    finally:
        h.close()


rid = 0x13
frames = [
    [rid, 0x04] + [0] * 15 + [0x49],
    [rid, 0x04] + [0] * 18,
    [rid, 0x00] + [0] * 18,
    [rid, 0x05] + [0] * 18,
    [rid, 0x02] + [0] * 18,
    [rid, 0x01] + [0] * 18,
]
run("K98", frames, 0x3554, 0xFA09, 0xFF02, 0x0002)
