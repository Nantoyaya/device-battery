"""Interactive HID explorer for the three target devices.

Usage:
  python explore.py listen  AULA|K98|VGN [seconds]
  python explore.py feature AULA|K98|VGN [id_min] [id_max]
  python explore.py send    AULA|K98|VGN <report_id_hex> <hex payload...>
  python explore.py raw     AULA|K98|VGN <hex bytes>
"""

import os
import sys
import time
import binascii

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hid_win

DEVICES = {
    "AULA": (0x249A, 0x5C2F, 0xFF01, 0x0010),
    "K98": (0x3554, 0xFA09, 0xFF02, 0x0002),
    "K98F": (0x3554, 0xFA09, 0xFF04, 0x0002),
    "VGN": (0x372E, 0x10BB, 0x000C, 0x0001),
}


def open_dev(key):
    vid, pid, page, usage = DEVICES[key]
    cands = [d for d in hid_win.find(vid, pid, page, usage) if not (d.usage_page == 0x000C and d.in_len == 3)]
    if not cands:
        raise SystemExit("device %s not found" % key)
    dev = cands[0]
    print("# %s %s in/out/feat=%d/%d/%d %r" % (key, dev.vidpid, dev.in_len, dev.out_len, dev.feat_len, dev.product))
    return hid_win.HidDevice(dev)


def hx(data, limit=None):
    if data is None:
        return "None"
    data = bytes(data)
    if limit:
        data = data[:limit]
    return " ".join("%02X" % b for b in data)


def cmd_listen(key, seconds=3.0):
    h = open_dev(key)
    try:
        print("listening %ss ..." % seconds)
        end = time.time() + seconds
        while time.time() < end:
            r = h.read_input(200)
            if r:
                print("  IN  " + hx(r))
    finally:
        h.close()


def cmd_feature(key, lo=0, hi=16):
    h = open_dev(key)
    try:
        n = h.info.feat_len or 16
        for rid in range(lo, hi + 1):
            r = h.get_feature(rid, n)
            if r and any(r[1:]):
                print("  FEAT id=%02X -> %s" % (rid, hx(r)))
            elif r:
                print("  FEAT id=%02X -> (all zero, %d bytes)" % (rid, len(r)))
    finally:
        h.close()


def cmd_send(key, rid, payload):
    h = open_dev(key)
    try:
        n = h.info.out_len or 33
        buf = bytes([rid]) + bytes.fromhex(payload)
        buf = buf + bytes(max(0, n - len(buf)))
        print("  OUT " + hx(buf))
        ok = h.write_output(buf[:n])
        print("  write ok=%s" % ok)
        end = time.time() + 0.6
        while time.time() < end:
            r = h.read_input(150)
            if r:
                print("  IN  " + hx(r))
    finally:
        h.close()


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return
    cmd, key = sys.argv[1], sys.argv[2].upper()
    if cmd == "listen":
        cmd_listen(key, float(sys.argv[3]) if len(sys.argv) > 3 else 3.0)
    elif cmd == "feature":
        lo = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0
        hi = int(sys.argv[4], 0) if len(sys.argv) > 4 else 16
        cmd_feature(key, lo, hi)
    elif cmd == "send":
        cmd_send(key, int(sys.argv[3], 0), sys.argv[4] if len(sys.argv) > 4 else "")
    elif cmd == "raw":
        cmd_send(key, int(sys.argv[3], 16), sys.argv[4] if len(sys.argv) > 4 else "")
    else:
        print(__doc__)


main()
