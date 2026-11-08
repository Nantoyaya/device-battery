"""写 feature 0xED + 监听 0xFD，看 dongle 是不是"命令走 feature、数据走 input"的设计。"""
import ctypes
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hid_win
from hid_win import HIDDLL

dev = [d for d in hid_win.find(0x372E, 0x10BB, 0x000C, 0x0001) if d.in_len == 32][0]
h = hid_win.HidDevice(dev)
try:
    h.drain_input(40)
    for cmd in range(0, 256):
        buf = ctypes.create_string_buffer(16)
        buf[0] = b"\xed"
        buf[1] = bytes([cmd])
        HIDDLL.HidD_SetFeature(h._h_rw, buf, 16)
        got = []
        end = time.time() + 0.06
        while time.time() < end:
            r = h.read_input(20)
            if r:
                got.append(r.hex(" "))
        if got:
            print("cmd=%02X -> %s" % (cmd, " || ".join(got)))
            sys.stdout.flush()
finally:
    h.close()
print("done")
