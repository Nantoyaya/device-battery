# -*- coding: utf-8 -*-
"""make_icon.py —— 生成多尺寸 .ico（纯标准库，手写 BMP/ICO 结构）。

画一个深色圆角方块 + 绿色电池，用作桌面快捷方式图标。
按 4x 超采样做抗锯齿，导出 16/32/48/64/128/256 六个尺寸。
"""

import os
import struct

SIZES = [256, 128, 64, 48, 32, 16]
SS = 4  # 超采样倍数


def sd_round_rect(px, py, x1, y1, x2, y2, r):
    """圆角矩形的有符号距离（<0 在内部）。"""
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    hx, hy = (x2 - x1) / 2.0 - r, (y2 - y1) / 2.0 - r
    dx = abs(px - cx) - hx
    dy = abs(py - cy) - hy
    ax, ay = max(dx, 0.0), max(dy, 0.0)
    return (ax * ax + ay * ay) ** 0.5 + min(max(dx, dy), 0.0) - r


def render(size):
    """返回 size×size 的 RGBA 像素（list[list[(r,g,b,a)]]）。"""
    S = float(size)
    out = [[(0, 0, 0, 0)] * size for _ in range(size)]

    plate = (0x16 / 255, 0x1a / 255, 0x22 / 255)
    edge = (0x2a / 255, 0x33 / 255, 0x44 / 255)
    green = (0x3d / 255, 0xdc / 255, 0x84 / 255)
    dark_green = (0x2a / 255, 0xa8 / 255, 0x63 / 255)

    inv = 1.0 / SS
    total = SS * SS
    for y in range(size):
        row = []
        for x in range(size):
            r_acc = g_acc = b_acc = a_acc = 0.0
            for sy in range(SS):
                for sx in range(SS):
                    px = (x + (sx + 0.5) * inv) / S
                    py = (y + (sy + 0.5) * inv) / S
                    col = sample(px, py, plate, edge, green, dark_green)
                    if col is None:
                        continue
                    r_acc += col[0]
                    g_acc += col[1]
                    b_acc += col[2]
                    a_acc += 1.0
            if a_acc <= 0:
                row.append((0, 0, 0, 0))
            else:
                n = a_acc
                row.append((int(r_acc / n * 255), int(g_acc / n * 255),
                            int(b_acc / n * 255), int(255 * n / total)))
        out[y] = row
    return out


def sample(px, py, plate, edge, green, dark_green):
    """单点采样，坐标系 0..1。返回 (r,g,b) 或 None。"""
    # 底板
    d = sd_round_rect(px, py, 0.035, 0.035, 0.965, 0.965, 0.20)
    if d > 0:
        return None
    base = plate
    if d > -0.012:
        base = edge

    # 电池外壳
    body = sd_round_rect(px, py, 0.30, 0.30, 0.70, 0.80, 0.075)
    shell = abs(body) - 0.028
    nub = sd_round_rect(px, py, 0.42, 0.19, 0.58, 0.30, 0.03)

    if nub < 0:
        return green
    if shell < 0:
        return green
    if body < 0:
        # 内部电量
        if py > 0.52:
            return dark_green if py > 0.66 else green
        return (0.10, 0.13, 0.18)
    return base


def bmp_bytes(pixels, size):
    """ICO 内嵌的 BMP（BITMAPINFOHEADER + BGRA 倒序 + AND mask）。"""
    header = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0,
                         size * size * 4, 0, 0, 0, 0)
    body = bytearray()
    for y in range(size - 1, -1, -1):
        for x in range(size):
            r, g, b, a = pixels[y][x]
            body += bytes((b, g, r, a))
    mask_row = ((size + 31) // 32) * 4
    body += bytes(mask_row * size)
    return header + bytes(body)


def main():
    images = []
    for size in SIZES:
        pixels = render(size)
        images.append((size, bmp_bytes(pixels, size)))

    out = bytearray()
    out += struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    for size, data in images:
        out += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32,
                           len(data), offset)
        offset += len(data)
    for _size, data in images:
        out += data

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "battery.ico")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(bytes(out))
    print("wrote", path, len(out), "bytes")


if __name__ == "__main__":
    main()
