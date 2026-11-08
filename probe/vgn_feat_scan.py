"""Probe the VGN dongle's feature report 0xED as a command channel."""

import ctypes
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hid_win
from hid_win import HIDDLL, K32

dev = [d for d in hid_win.find(0x372E, 0x10BB, 0x000C, 0x0001) if d.in_len == 32][0]
h = hid_win._open(dev.path, hid_win.GENERIC_READ | hid_win.GENERIC_WRITE, False)
print("handle", h, "feat_len", dev.feat_len)

base = ctypes.create_string_buffer(16)
base[0] = b"\xed"
HIDDLL.HidD_GetFeature(h, base, 16)
print("baseline", base.raw.hex(" "))

for cmd in range(0, 256):
    buf = ctypes.create_string_buffer(16)
    buf[0] = b"\xed"
    buf[1] = bytes([cmd])
    ok = HIDDLL.HidD_SetFeature(h, buf, 16)
    rb = ctypes.create_string_buffer(16)
    rb[0] = b"\xed"
    rok = HIDDLL.HidD_GetFeature(h, rb, 16)
    if rb.raw != base.raw or not ok:
        print("cmd=%02X set=%s get=%s  %s" % (cmd, ok, rok, rb.raw.hex(" ")))
    sys.stdout.flush()
K32.CloseHandle(h)
