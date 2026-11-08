import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hid_win

TARGETS = [
    ("AULA SC360se ?", 0x249A, 0x5C2F, 0xFF01, 0x0010),
    ("Lingbao K98 ?", 0x3554, 0xFA09, 0xFF02, 0x0002),
    ("VGN headset", 0x372E, 0x10BB, 0x000C, 0x0001),
]

KINDS = {hid_win.HIDP_INPUT: "IN", hid_win.HIDP_OUTPUT: "OUT", hid_win.HIDP_FEATURE: "FEAT"}

for name, vid, pid, page, usage in TARGETS:
    devs = hid_win.find(vid, pid, page, usage)
    for dev in devs:
        if dev.usage_page == 0x000C and dev.in_len == 3:
            continue
        print("=" * 90)
        print("%s  %s  caps in/out/feat = %d/%d/%d  %r" % (
            name, dev.vidpid, dev.in_len, dev.out_len, dev.feat_len, dev.product))
        try:
            with hid_win.HidDevice(dev) as h:
                for kind, label in KINDS.items():
                    vcs = h.value_caps(kind)
                    print("  %-4s value caps: %d" % (label, len(vcs)))
                    seen = {}
                    for vc in vcs:
                        key = (vc.ReportID, vc.UsagePage, vc.UsageMin if vc.IsRange else vc.UsageMin,
                               vc.BitSize, vc.ReportCount, vc.LogicalMin, vc.LogicalMax)
                        seen[key] = seen.get(key, 0) + 1
                    for key, cnt in sorted(seen.items()):
                        print("     id=%02X page=%04X usage=%04X bits=%d count=%d log=%d..%d (x%d)" % (
                            key[0], key[1], key[2], key[3], key[4], key[5], key[6], cnt))
        except OSError as exc:
            print("  open failed:", exc)
