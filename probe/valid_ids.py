import ctypes
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hid_win
from hid_win import K32

TARGETS = {
    "AULA": (0x249A, 0x5C2F, 0xFF01, 0x0010),
    "K98": (0x3554, 0xFA09, 0xFF02, 0x0002),
    "VGN": (0x372E, 0x10BB, 0x000C, 0x0001),
}

for key, (vid, pid, page, usage) in TARGETS.items():
    devs = [d for d in hid_win.find(vid, pid, page, usage) if not (d.usage_page == 0x000C and d.in_len == 3)]
    dev = devs[0]
    h = hid_win._open(dev.path, hid_win.GENERIC_READ | hid_win.GENERIC_WRITE, False)
    if not h:
        print(key, "cannot open rw, err", ctypes.get_last_error())
        continue
    print("==", key, dev.vidpid, "out_len", dev.out_len, "in_len", dev.in_len, "feat", dev.feat_len)
    valid = []
    for rid in range(0, 256):
        buf = bytearray(dev.out_len)
        buf[0] = rid
        b = ctypes.create_string_buffer(bytes(buf), len(buf))
        written = ctypes.c_uint32(0)
        ok = K32.WriteFile(h, b, len(buf), ctypes.byref(written), None)
        err = ctypes.get_last_error()
        if ok:
            valid.append(rid)
        elif err != 87:
            valid.append((rid, err))
    print("   writable report ids:", ["%02X" % v if isinstance(v, int) else v for v in valid])
    K32.CloseHandle(h)
