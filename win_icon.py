# -*- coding: utf-8 -*-
"""win_icon.py —— 把电量数字画成托盘图标（纯 ctypes + 点阵，不依赖 Pillow）。

思路：内置 3x5 点阵数字 → 渲染成 RGBA 位图 → 手写 ICO → LoadImageW 得到 HICON。
键盘图标带一块圆角底板，和鼠标图标区分开。
"""

from __future__ import annotations

import ctypes
import os
import struct
import tempfile
from ctypes import wintypes

# 3x5 点阵
DIGITS = {
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "001", "010", "010"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
    "?": ("111", "001", "011", "000", "010"),
    "-": ("000", "000", "111", "000", "000"),
}

GLYPH_W, GLYPH_H = 3, 5
SIZES = (16, 24, 32, 48)


def _fit(text, size):
    """选一个能塞进 size 的最大缩放倍数。"""
    n = len(text)
    gap = 1
    scale = 1
    while True:
        w = n * GLYPH_W * (scale + 1) + (n - 1) * gap
        h = GLYPH_H * (scale + 1)
        if w > size - 2 or h > size - 2:
            return scale, gap
        scale += 1


def render_rgba(text, size, color, plate=False):
    """返回 size*size*4 的 RGBA 字节（行优先）。"""
    scale, gap = _fit(text, size)
    gw, gh = GLYPH_W * scale, GLYPH_H * scale
    total_w = len(text) * gw + (len(text) - 1) * gap
    total_h = gh
    ox = (size - total_w) // 2
    oy = (size - total_h) // 2

    px = bytearray(size * size * 4)

    def put(x, y, rgba):
        if 0 <= x < size and 0 <= y < size:
            i = (y * size + x) * 4
            px[i:i + 4] = bytes(rgba)

    def alpha(x, y):
        return px[(y * size + x) * 4 + 3]

    if plate:
        radius = max(2, size // 6)
        for y in range(size):
            for x in range(size):
                cx = min(x, size - 1 - x)
                cy = min(y, size - 1 - y)
                if cx < radius and cy < radius and (radius - cx) ** 2 + (radius - cy) ** 2 > radius ** 2:
                    continue
                put(x, y, (24, 28, 36, 235))

    for k, ch in enumerate(text):
        glyph = DIGITS.get(ch)
        if not glyph:
            continue
        gx = ox + k * (gw + gap)
        for gy, row in enumerate(glyph):
            for gxx, bit in enumerate(row):
                if bit == "1":
                    for dy in range(scale):
                        for dx in range(scale):
                            put(gx + gxx * scale + dx, oy + gy * scale + dy, (*color, 255))

    # 深色描边，保证浅色任务栏上也清楚
    edge = []
    for y in range(size):
        for x in range(size):
            if alpha(x, y) == 0:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < size and 0 <= ny < size and alpha(nx, ny) == 0:
                    edge.append((nx, ny))
    for x, y in edge:
        if alpha(x, y) == 0:
            put(x, y, (16, 18, 22, 190))
    return bytes(px)


def build_ico(images):
    """把 [(size, rgba), ...] 打包成 ICO 文件内容。"""
    entries, blobs = [], []
    offset = 6 + 16 * len(images)
    for size, rgba in images:
        bih = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0,
                          size * size * 4, 0, 0, 0, 0)
        xor = bytearray()
        for y in range(size - 1, -1, -1):
            row = rgba[y * size * 4:(y + 1) * size * 4]
            for x in range(size):
                r, g, b, a = row[x * 4:x * 4 + 4]
                xor += bytes((b, g, r, a))
        mask = b"\x00" * (((size + 31) // 32) * 4 * size)
        blob = bih + bytes(xor) + mask
        blobs.append(blob)
        entries.append(struct.pack("<BBBBHHII", size if size < 256 else 0,
                                   size if size < 256 else 0, 0, 0, 1, 32,
                                   len(blob), offset))
        offset += len(blob)
    return struct.pack("<HHH", 0, 1, len(images)) + b"".join(entries) + b"".join(blobs)


USER32 = ctypes.WinDLL("user32", use_last_error=True)
USER32.LoadImageW.restype = ctypes.c_void_p
USER32.LoadImageW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, wintypes.UINT,
                              ctypes.c_int, ctypes.c_int, wintypes.UINT]
USER32.DestroyIcon.argtypes = [ctypes.c_void_p]

IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010

_cache = {}
_tmp_dir = None


def _tmp():
    global _tmp_dir
    if _tmp_dir is None:
        _tmp_dir = os.path.join(tempfile.gettempdir(), "device_battery_icons")
        os.makedirs(_tmp_dir, exist_ok=True)
    return _tmp_dir


def make_hicon(text, color, plate=False):
    """生成（带缓存的）HICON；失败返回 0。"""
    key = (text, tuple(color), bool(plate))
    if key in _cache:
        return _cache[key]
    ico = build_ico([(s, render_rgba(text, s, color, plate)) for s in SIZES])
    name = "ic_%s_%02x%02x%02x_%d.ico" % (text.replace("?", "q"), color[0], color[1], color[2], int(plate))
    path = os.path.join(_tmp(), name)
    try:
        with open(path, "wb") as f:
            f.write(ico)
    except OSError:
        return 0
    h = USER32.LoadImageW(None, path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE)
    hicon = int(h) if h else 0
    _cache[key] = hicon
    return hicon


def render_ring(level, size, color, track=(96, 107, 126), thickness=None):
    """电量环：从 12 点开始顺时针填充，3x 超采样抗锯齿。"""
    ss = 3
    inv = 1.0 / ss
    c = (size - 1) / 2.0
    r_out = size / 2.0 - 0.4
    t = thickness if thickness else max(1.6, size * 0.16)
    r_in = r_out - t
    level = max(0, min(100, level or 0))
    sweep = level / 100.0 * 6.283185307179586

    px = bytearray(size * size * 4)
    for y in range(size):
        for x in range(size):
            acc_a = 0.0
            acc_r = acc_g = acc_b = 0.0
            for sy in range(ss):
                for sx in range(ss):
                    fx = x + (sx + 0.5) * inv - c
                    fy = y + (sy + 0.5) * inv - c
                    d = (fx * fx + fy * fy) ** 0.5
                    if d > r_out or d < r_in:
                        continue
                    ang = _angle_from_top(fx, fy)
                    col = color if ang <= sweep else track
                    acc_r += col[0]
                    acc_g += col[1]
                    acc_b += col[2]
                    acc_a += 1.0
            if acc_a > 0:
                n = acc_a
                i = (y * size + x) * 4
                px[i:i + 4] = bytes((int(acc_r / n), int(acc_g / n), int(acc_b / n),
                                     int(255 * acc_a / (ss * ss))))
    return bytes(px)


def _angle_from_top(dx, dy):
    """从 12 点方向起、顺时针的角度（0..2π）。"""
    import math
    a = math.atan2(dx, -dy)
    if a < 0:
        a += 6.283185307179586
    return a


def make_ring_hicon(level, color):
    key = ("ring", int(level or 0), tuple(color))
    if key in _cache:
        return _cache[key]
    ico = build_ico([(s, render_ring(level, s, color)) for s in SIZES])
    path = os.path.join(_tmp(), "ring_%03d_%02x%02x%02x.ico" % (int(level or 0),
                                                                color[0], color[1], color[2]))
    try:
        with open(path, "wb") as f:
            f.write(ico)
    except OSError:
        return 0
    h = USER32.LoadImageW(None, path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE)
    hicon = int(h) if h else 0
    _cache[key] = hicon
    return hicon


def destroy_all():
    for hicon in _cache.values():
        if hicon:
            try:
                USER32.DestroyIcon(ctypes.c_void_p(hicon))
            except Exception:
                pass
    _cache.clear()


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
    os.makedirs(out, exist_ok=True)
    for text, color, plate, name in (("95", (61, 220, 132), False, "tray_mouse_95"),
                                     ("100", (61, 220, 132), True, "tray_kb_100"),
                                     ("8", (255, 93, 93), False, "tray_mouse_8")):
        with open(os.path.join(out, name + ".ico"), "wb") as f:
            f.write(build_ico([(s, render_rgba(text, s, color, plate)) for s in SIZES]))
        print("wrote", name)
