import os
import sys
import ctypes
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hid_win
from hid_win import HIDDLL, K32


def scan_features(vid, pid, page, usage, length, ids=range(0, 256)):
    devs = [d for d in hid_win.find(vid, pid, page, usage) if not (d.usage_page == 0x000C and d.in_len == 3)]
    dev = devs[0]
    print("==", dev.vidpid, "feat_len", dev.feat_len)
    h = hid_win._open(dev.path, hid_win.GENERIC_READ | hid_win.GENERIC_WRITE, False) or hid_win._open(dev.path, 0, False)
    hits = []
    try:
        for rid in ids:
            buf = ctypes.create_string_buffer(length)
            buf[0] = bytes([rid])
            if HIDDLL.HidD_GetFeature(h, buf, length):
                data = buf.raw
                if any(data[1:]):
                    hits.append((rid, data))
                    print("  id=%02X  %s" % (rid, " ".join("%02X" % b for b in data)))
                else:
                    print("  id=%02X  zeros" % rid)
    finally:
        K32.CloseHandle(h)
    return hits


scan_features(0x3554, 0xFA09, 0xFF04, 0x0002, 8)
print()
scan_features(0x372E, 0x10BB, 0x000C, 0x0001, 16)
