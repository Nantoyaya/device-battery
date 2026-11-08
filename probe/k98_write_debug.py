import ctypes
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hid_win
from hid_win import HIDDLL, K32

HIDDLL.HidD_SetOutputReport.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
HIDDLL.HidD_SetOutputReport.restype = ctypes.c_bool

dev = [d for d in hid_win.find(0x3554, 0xFA09, 0xFF02, 0x0002)][0]
print("path", dev.path)

for access, name in ((0, "0"), (hid_win.GENERIC_READ, "R"), (hid_win.GENERIC_READ | hid_win.GENERIC_WRITE, "RW")):
    h = hid_win._open(dev.path, access, False)
    err = ctypes.get_last_error()
    print("open", name, "->", h, "err", err)
    if not h:
        continue
    buf = bytes([0x08, 0x04] + [0] * 15 + [0x49])
    b = ctypes.create_string_buffer(buf, len(buf))
    wr = ctypes.c_uint32(0)
    ok = K32.WriteFile(h, b, len(buf), ctypes.byref(wr), None)
    print("   WriteFile ok", ok, "err", ctypes.get_last_error(), "written", wr.value)
    ok2 = HIDDLL.HidD_SetOutputReport(h, b, len(buf))
    print("   SetOutputReport ok", ok2, "err", ctypes.get_last_error())
    K32.CloseHandle(h)
