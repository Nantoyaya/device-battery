import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hid_win


def crc16_ccitt_false(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def jl_frame(seq, tlv, more=0x00, cmd=0x02, direction=0x10):
    """00 FE seq <dir> 00 <cmd> frag more len_LE16 <tlv> crc_be16"""
    body = bytes([direction, 0x00, cmd, 0x00, more]) + len(tlv).to_bytes(2, "little") + bytes(tlv)
    head = bytes([0x00, 0xFE, seq & 0xFF])
    frame = bytearray(head + body)
    frame += bytes(16)
    crc = crc16_ccitt_false(frame[1:10 + len(tlv)])
    frame[10 + len(tlv)] = (crc >> 8) & 0xFF
    frame[11 + len(tlv)] = crc & 0xFF
    return bytes(frame)


def show(tag, data):
    print("%-18s %s" % (tag, " ".join("%02X" % b for b in data)))


dev = [d for d in hid_win.find(0x372E, 0x10BB, 0x000C, 0x0001) if d.in_len == 32][0]
h = hid_win.HidDevice(dev)
try:
    print("out_len", dev.out_len, "in_len", dev.in_len, "feat_len", dev.feat_len)
    h.drain_input(30)

    for rid in (0xFD, 0x00, 0x08):
        for seq in (0, 1):
            for tlv in (b"\x01", b"\x01\x00"):
                frame = jl_frame(seq, tlv)
                buf = bytearray(dev.out_len)
                buf[0] = rid
                buf[1:1 + len(frame)] = frame
                show("OUT rid=%02X seq=%d" % (rid, seq), bytes(buf))
                ok = h.write_output(bytes(buf))
                print("   write ok", ok)
                end = time.time() + 0.35
                while time.time() < end:
                    r = h.read_input(120)
                    if r:
                        show("   IN", r)
finally:
    h.close()
