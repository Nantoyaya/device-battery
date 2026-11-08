import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hid_win


ITEMS = {
    0x04: "UsagePage", 0x08: "Usage", 0x14: "LogicalMin", 0x24: "LogicalMax",
    0x34: "PhysicalMin", 0x44: "PhysicalMax", 0x74: "ReportSize", 0x84: "ReportID",
    0x94: "ReportCount", 0xA4: "Push", 0xB4: "Pop",
    0x80: "Input", 0x90: "Output", 0xB0: "Feature", 0xA0: "Collection",
    0xC0: "EndCollection",
}


def parse(desc):
    """Very small HID report descriptor walker: yields (kind, report_id, bit_size) runs."""
    i = 0
    g_usage_page = 0
    usage = 0
    report_id = 0
    rsize = 0
    rcount = 0
    stack = []
    while i < len(desc):
        b = desc[i]
        i += 1
        if b == 0xFE:  # long item
            if i + 2 > len(desc):
                break
            dsize = desc[i]
            i += 1 + 1 + dsize
            continue
        size = {0: 0, 1: 1, 2: 2, 3: 4}.get(b & 0x03, 0)
        tag = b & 0xFC
        data = 0
        for k in range(size):
            if i < len(desc):
                data |= desc[i] << (8 * k)
                i += 1
        if tag == 0x04:
            g_usage_page = data
        elif tag == 0x08:
            usage = (g_usage_page << 16) | data
        elif tag == 0x84:
            report_id = data
        elif tag == 0x74:
            rsize = data
        elif tag == 0x94:
            rcount = data
        elif tag in (0x80, 0x90, 0xB0):
            kind = {0x80: "IN", 0x90: "OUT", 0xB0: "FEAT"}[tag]
            yield kind, report_id, rsize * rcount, rcount, usage
        elif tag == 0xA4:
            stack.append((g_usage_page, usage))
        elif tag == 0xB4:
            if stack:
                g_usage_page, usage = stack.pop()


for dev in hid_win.enumerate_hid():
    if dev.vid not in (0x249A, 0x3554, 0x372E):
        continue
    print("=" * 100)
    print("%s  page=%04X usage=%04X  in=%d out=%d feat=%d  %r / %r" % (
        dev.vidpid, dev.usage_page or 0, dev.usage or 0, dev.in_len or 0,
        dev.out_len or 0, dev.feat_len or 0, dev.product, dev.manufacturer))
    print("   " + dev.path)
    try:
        with hid_win.HidDevice(dev) as h:
            desc = h.report_descriptor()
    except OSError as exc:
        print("   open failed:", exc)
        continue
    print("   descriptor %d bytes: %s" % (len(desc), desc.hex(" ")))
    for kind, rid, bits, count, usage in parse(desc):
        if kind != "FEAT" or True:
            print("      %-4s id=%02X bits=%d count=%d usage=%04X:%04X bytes=%d" % (
                kind, rid, bits, count, (usage >> 16) & 0xFFFF, usage & 0xFFFF, bits // 8))
