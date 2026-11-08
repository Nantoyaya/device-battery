import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hid_win


def try_frames(key, frames, gap=0.5):
    vid, pid, page, usage = {
        "AULA": (0x249A, 0x5C2F, 0xFF01, 0x0010),
        "K98": (0x3554, 0xFA09, 0xFF02, 0x0002),
        "VGN": (0x372E, 0x10BB, 0x000C, 0x0001),
    }[key]
    cands = [d for d in hid_win.find(vid, pid, page, usage) if not (d.usage_page == 0x000C and d.in_len == 3)]
    dev = cands[0]
    print("==", key, dev.vidpid, "out", dev.out_len)
    h = hid_win.HidDevice(dev)
    try:
        h.drain_input(50)
        for frame in frames:
            buf = bytearray(dev.out_len)
            buf[0:len(frame)] = frame
            ok = h.write_output(bytes(buf))
            print("OUT %-40s ok=%s" % (bytes(frame).hex(" "), ok))
            end = time.time() + gap
            while time.time() < end:
                r = h.read_input(120)
                if r:
                    print("   IN  %s" % r.hex(" "))
    finally:
        h.close()


atk = [0x08, 0x7D, 0x72, 0x02, 0x00, 0x01, 0x07, 0x01]
frames = [
    atk,
    [0x08, 0x7D, 0x72, 0x02],
    [0x08, 0x7D, 0x75],
    [0x08, 0x7D, 0x75, 0x00],
    [0x08, 0x7D, 0x74, 0x00],
    [0x08, 0x7D, 0x73, 0x00],
    [0x08, 0x7D, 0x7D, 0x00],
]

try_frames(sys.argv[1].upper() if len(sys.argv) > 1 else "AULA", frames)
