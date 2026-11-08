import os
import sys
import ctypes
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hid_win
from hid_win import K32, HIDDLL

dev = [d for d in hid_win.find(0x372E, 0x10BB, 0x000C, 0x0001) if d.in_len == 32][0]
print("path", dev.path)

for access, name in ((0, "read-only"), (hid_win.GENERIC_READ, "read"), (hid_win.GENERIC_READ | hid_win.GENERIC_WRITE, "rw")):
    h = hid_win._open(dev.path, access, False)
    print(name, "handle", h)
    if not h:
        print("   err", ctypes.get_last_error())
        continue
    for rid, ln in ((0xED, 16), (6, 8), (0, 16)):
        buf = ctypes.create_string_buffer(ln)
        buf[0] = bytes([rid])
        ok = HIDDLL.HidD_GetFeature(h, buf, ln)
        print("   getfeat id=%02X len=%d ok=%s err=%d data=%s" % (
            rid, ln, ok, ctypes.get_last_error(), buf.raw.hex(" ")))
    K32.CloseHandle(h)
