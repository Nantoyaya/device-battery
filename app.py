# -*- coding: utf-8 -*-
"""app.py —— 设备电量面板（tkinter + ctypes，纯标准库）。

界面：卡片（设备图标 / 电量 / 历史曲线 / 进度条）+ 可展开的设置页；
托盘：每台设备一个图标，左键开面板、右键菜单；关窗只收进托盘。
"""

from __future__ import annotations

import argparse
import ctypes
import math
import queue
import threading
import time
import tkinter as tk
from ctypes import wintypes
from tkinter import font as tkfont

import battery
import config
import devices
import tray as tray_mod
import win_shell

# ---- 配色 ---------------------------------------------------------------
BG = "#0f1218"
BG_SOFT = "#141922"
CARD = "#171c25"
CARD_EDGE = "#242c3a"
TEXT = "#e9eef7"
SUB = "#8b96a8"
DIM = "#5d6676"
GREEN = "#3ddc84"
AMBER = "#ffb020"
RED = "#ff5d5d"
ACCENT = "#5b8cff"
CHIP = "#1b2130"
CHIP_ON = "#25314a"

MUTEX_NAME = "Local\\DeviceBatteryPanel_single_instance"
WINDOW_TITLE = "设备电量"
W, H_BASE, H_OPEN = 560, 452, 604

GLYPHS = {}


def level_color(level):
    if level >= 60:
        return GREEN
    if level >= 30:
        return AMBER
    return RED


def round_rect(cv, x1, y1, x2, y2, r, **kw):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [
        x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1,
        x2, y1 + r, x2, y1 + r, x2, y2 - r, x2, y2 - r, x2, y2,
        x2 - r, y2, x2 - r, y2, x1 + r, y2, x1 + r, y2, x1, y2,
        x1, y2 - r, x1, y2 - r, x1, y1 + r, x1, y1 + r, x1, y1,
    ]
    return cv.create_polygon(pts, smooth=True, splinesteps=28, **kw)


def draw_mouse(cv, x, y, w, h, color):
    """鼠标小图标。"""
    round_rect(cv, x, y, x + w, y + h, w / 2.2, fill="", outline=color, width=2)
    cv.create_line(x + 1, y + h * 0.42, x + w - 1, y + h * 0.42, fill=color, width=1)
    cv.create_line(x + w / 2, y + h * 0.10, x + w / 2, y + h * 0.28, fill=color, width=2)


def draw_keyboard(cv, x, y, w, h, color):
    """键盘小图标。"""
    round_rect(cv, x, y + h * 0.18, x + w, y + h * 0.82, 4, fill="", outline=color, width=2)
    rows = 3
    cols = 5
    pad = 3
    bw = (w - pad * (cols + 1)) / cols
    bh = (h * 0.64 - pad * (rows + 1)) / rows
    for r in range(rows):
        for c in range(cols):
            if r == 2 and 1 <= c <= 3:
                continue
            bx = x + pad + c * (bw + pad)
            by = y + h * 0.18 + pad + r * (bh + pad)
            cv.create_rectangle(bx, by, bx + bw, by + bh, fill=color, outline="")
    cv.create_rectangle(x + w * 0.3, y + h * 0.66, x + w * 0.7, y + h * 0.66 + bh,
                        fill=color, outline="")


class Card:
    W, H = 512, 124

    def __init__(self, master, cls, fonts):
        self.cls = cls
        self.fonts = fonts
        self.cv = tk.Canvas(master, width=self.W, height=self.H, bg=BG,
                            highlightthickness=0, bd=0)
        self.reading = None
        self.stamp = None
        self.history = []          # [(t, level)]
        self.shown = 0.0           # 当前动画到的数值
        self.target = 0.0
        self.has_value = False
        self.hover = False
        self.cv.bind("<Enter>", self._on_enter)
        self.cv.bind("<Leave>", self._on_leave)
        self.draw()

    def _on_enter(self, _e=None):
        self.hover = True
        self.draw()

    def _on_leave(self, _e=None):
        self.hover = False
        self.draw()

    # -- 数据 ------------------------------------------------------------
    def update(self, reading, when=None):
        self.reading = reading
        self.stamp = when
        if reading and reading.ok:
            self.history.append((time.time(), reading.level))
            if len(self.history) > 60:
                self.history.pop(0)
            self.target = float(reading.level)
            if not self.has_value:
                self.shown = self.target
                self.has_value = True
        else:
            self.has_value = False
        self.draw()

    def animate(self):
        """返回是否还需要继续动画。"""
        if not self.has_value:
            return False
        diff = self.target - self.shown
        if abs(diff) < 0.4:
            self.shown = self.target
            return False
        self.shown += diff * 0.28
        self.draw()
        return True

    # -- 绘制 ------------------------------------------------------------
    def draw(self):
        cv, W, H = self.cv, self.W, self.H
        cv.delete("all")
        round_rect(cv, 0.5, 0.5, W - 0.5, H - 1.5, 14,
                   fill=CARD, outline="#33405a" if self.hover else CARD_EDGE, width=1)

        r = self.reading
        ok = bool(r and r.ok)
        level = r.level if ok else None
        color = level_color(level) if ok else "#3a4150"

        # 顶部：设备图标 + 名称 + 标签
        glyph = (18, 34, 22, 40)
        if self.cls.KIND == "键盘":
            draw_keyboard(cv, 18, 36, 26, 26, "#6b7688")
        else:
            draw_mouse(cv, 22, 34, 18, 34, "#6b7688")

        name = cv.create_text(58, 21, text=self.cls.NAME, anchor="w",
                              fill=TEXT, font=self.fonts["name"])
        x = cv.bbox(name)[2] + 10
        tags = [self.cls.KIND]
        if r and r.mode:
            tags.append(r.mode)
        if r and r.charging:
            tags.append("充电中")
        for tag in tags:
            fg = ACCENT if tag == self.cls.KIND else (GREEN if tag == "充电中" else SUB)
            t = cv.create_text(x + 9, 21, text=tag, anchor="w", fill=fg,
                               font=self.fonts["pill"])
            w = cv.bbox(t)[2] - x
            round_rect(cv, x, 12, x + w + 10, 30, 9, fill=CHIP, outline="")
            cv.tag_lower(cv.find_all()[-1], t)
            x += w + 16

        if self.stamp:
            cv.create_text(W - 20, 21, text=self.stamp, anchor="e",
                           fill=DIM, font=self.fonts["meta"])

        # 左下：大号电量 + 电池图标
        self.draw_battery(22, 44, 26, 42, color, int(round(self.shown)) if ok else None)
        if ok:
            num = cv.create_text(62, 70, text="%d" % int(round(self.shown)), anchor="w",
                                 fill=color, font=self.fonts["level"])
            nx = cv.bbox(num)[2]
            cv.create_text(nx + 2, 77, text="%", anchor="w", fill=color,
                           font=self.fonts["pct"])
        else:
            cv.create_text(62, 68, text="—", anchor="w", fill=DIM, font=self.fonts["level"])
            cv.create_text(112, 74, text="未读取", anchor="w", fill=DIM,
                           font=self.fonts["small"])

        # 右侧：历史曲线
        self.draw_spark(352, 40, 138, 40, color if ok else "#39404e")

        # 进度条
        bar_x1, bar_x2, bar_y = 22, W - 22, 100
        round_rect(cv, bar_x1, bar_y, bar_x2, bar_y + 7, 3.5, fill="#202631", outline="")
        if ok and self.shown > 0:
            fill_w = max(8.0, (bar_x2 - bar_x1) * self.shown / 100.0)
            round_rect(cv, bar_x1, bar_y, bar_x1 + fill_w, bar_y + 7, 3.5,
                       fill=color, outline="")

        # 说明
        if r is None:
            text, fg = "正在读取…", SUB
        elif ok:
            text, fg = r.source, SUB
            if r.note:
                text = "%s   ·   %s" % (text, r.note)
        else:
            text = r.error + ("   ·   " + r.retries_hint if r.retries_hint else "")
            fg = "#e0a44a"
        cv.create_text(22, 117, text=text, anchor="w", fill=fg, font=self.fonts["small"])

    def draw_battery(self, x, y, w, h, color, level):
        cv = self.cv
        round_rect(cv, x + w / 2 - 4, y - 4, x + w / 2 + 4, y + 1, 2, fill=color, outline="")
        round_rect(cv, x, y, x + w, y + h, 6, fill="", outline=color, width=2)
        if level:
            inset = 4
            inner_h = (h - inset * 2) * max(0, min(100, level)) / 100.0
            if inner_h >= 2:
                round_rect(cv, x + inset, y + h - inset - inner_h,
                           x + w - inset, y + h - inset, 2.5, fill=color, outline="")

    def draw_spark(self, x, y, w, h, color):
        """最近若干次读数的迷你折线。"""
        cv = self.cv
        # 参考网格
        for gy in (y + h * 0.0, y + h * 0.5, y + h):
            cv.create_line(x, gy, x + w, gy, fill="#1e2531", width=1)
        pts = [lv for _t, lv in self.history[-24:]]
        if len(pts) < 3:
            mid = y + h / 2
            dash = 5
            xx = x
            while xx < x + w - dash:
                cv.create_line(xx, mid, xx + dash, mid, fill="#333c4e", width=1)
                xx += dash * 2
            cv.create_text(x + w, mid - 8, text="趋势采样中", anchor="e",
                           fill="#3f485a", font=self.fonts["meta"])
            return
        n = len(pts)
        step = w / float(n - 1)
        coords = []
        for i, lv in enumerate(pts):
            px = x + i * step
            py = y + h - (h * max(0, min(100, lv)) / 100.0)
            coords.extend([px, py])
        area = coords + [x + w, y + h, x, y + h]
        cv.create_polygon(area, fill="#1a2130", outline="")
        cv.create_line(*coords, fill=color, width=2, smooth=True)
        cv.create_oval(coords[-2] - 2.5, coords[-1] - 2.5, coords[-2] + 2.5, coords[-1] + 2.5,
                       fill=color, outline="")


class Chip(tk.Label):
    """设置页里的小胶囊按钮。"""

    def __init__(self, master, text, command, selected=False, font=None):
        super().__init__(master, text=text, font=font, padx=11, pady=4,
                         bg=CHIP_ON if selected else CHIP,
                         fg=TEXT if selected else SUB, cursor="hand2")
        self._command = command
        self._selected = selected
        self.bind("<Button-1>", lambda _e: self._command(self))
        self.bind("<Enter>", self._hover_on)
        self.bind("<Leave>", self._hover_off)

    def _hover_on(self, _e=None):
        if not self._selected:
            self.configure(bg="#232b3d")

    def _hover_off(self, _e=None):
        if not self._selected:
            self.configure(bg=CHIP)

    def set_selected(self, value):
        self._selected = value
        self.configure(bg=CHIP_ON if value else CHIP, fg=TEXT if value else SUB)


class App:
    INTERVALS = [(30, "30 秒"), (60, "1 分钟"), (120, "2 分钟"),
                 (300, "5 分钟"), (600, "10 分钟")]

    def __init__(self, root, start_hidden=False):
        self.root = root
        self.cfg = config.load()
        self.q = queue.Queue()
        self.actions = queue.Queue()
        self.job = battery.ReadingJob(self.q)
        self.busy = False
        self.settings_open = False
        self.alerted = {}

        self.autostart = win_shell.autostart_enabled()
        if not self.autostart:
            self.autostart = win_shell.enable_autostart()

        root.title(WINDOW_TITLE)
        root.configure(bg=BG)
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        self.center(W, H_BASE)

        self.build_fonts()
        self.apply_dark_titlebar()
        self.set_window_icon()
        self.build_ui()
        self.start_tray()

        root.bind("<F5>", lambda _e: self.refresh())
        root.bind("<Escape>", lambda _e: self.hide_to_tray())

        if start_hidden:
            root.withdraw()
        self.refresh()
        self.schedule()
        self.root.after(120, self.pump)
        self.root.after(30, self.tick_animation)

    # -- 基础 ------------------------------------------------------------
    def center(self, w, h):
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = max(0, (sh - h) // 2 - 40)
        self.root.geometry("%dx%d+%d+%d" % (w, h, x, y))

    def build_fonts(self):
        family = self.pick_font(["Microsoft YaHei UI", "微软雅黑", "Microsoft YaHei", "Segoe UI"])
        num = self.pick_font(["Bahnschrift", "Segoe UI Semibold", "Segoe UI"])
        self.fonts = {
            "title": (family, 16, "bold"),
            "subtitle": (family, 9),
            "name": (family, 11, "bold"),
            "pill": (family, 8),
            "level": (num, 34, "bold"),
            "pct": (family, 15, "bold"),
            "meta": (family, 8),
            "small": (family, 8),
            "body": (family, 9),
            "chip": (family, 9),
            "section": (family, 9, "bold"),
        }

    def pick_font(self, candidates):
        available = set(tkfont.families())
        for name in candidates:
            if name in available:
                return name
        return "TkDefaultFont"

    def apply_dark_titlebar(self):
        """Win10/11 的深色标题栏，让系统边框和深色界面统一。"""
        try:
            self.root.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            value = ctypes.c_int(1)
            for attr in (20, 19):          # DWMWA_USE_IMMERSIVE_DARK_MODE / 老版本
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(value), ctypes.sizeof(value))
        except Exception:
            pass

    def set_window_icon(self):
        ico = win_shell.icon_path()
        if ico and win_shell.os.path.exists(ico):
            try:
                self.root.iconbitmap(ico)
            except Exception:
                pass

    # -- 布局 ------------------------------------------------------------
    def build_ui(self):
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=22, pady=(14, 6))
        tk.Label(header, text="设备电量", bg=BG, fg=TEXT, font=self.fonts["title"]).pack(side="left")
        tk.Label(header, text="  2.4G 外设 · 本地 HID", bg=BG, fg=DIM,
                 font=self.fonts["subtitle"]).pack(side="left", pady=(6, 0))

        self.gear = self.make_icon_button(header, "⚙", self.toggle_settings)
        self.gear.pack(side="right", pady=(2, 0))

        cards = tk.Frame(self.root, bg=BG)
        cards.pack(fill="x", padx=22)
        self.cards = {}
        self.order = list(devices.ALL_DEVICES)
        for cls in self.order:
            card = Card(cards, cls, self.fonts)
            card.cv.pack(fill="x", pady=(0, 8))
            self.cards[cls] = card

        self.settings = tk.Frame(self.root, bg=BG_SOFT,
                                 highlightbackground=CARD_EDGE, highlightthickness=1)
        self.build_settings(self.settings)

        bottom = tk.Frame(self.root, bg=BG)
        bottom.pack(fill="x", padx=22, pady=(2, 12))
        self.bottom = bottom
        self.status = tk.Label(bottom, text="准备中…", bg=BG, fg=DIM,
                               font=self.fonts["meta"], anchor="w")
        self.status.pack(side="left")

        self.refresh_btn = self.make_button(bottom, "立即刷新", self.refresh)
        self.refresh_btn.pack(side="right")
        self.interval_btn = self.make_button(bottom, self.interval_label(), self.cycle_interval)
        self.interval_btn.pack(side="right", padx=(0, 8))
        self.root.update_idletasks()
        self.resize_to_content()

    def build_settings(self, parent):
        pad = tk.Frame(parent, bg=BG_SOFT)
        pad.pack(fill="both", expand=True, padx=16, pady=12)

        tk.Label(pad, text="设置", bg=BG_SOFT, fg=TEXT,
                 font=self.fonts["section"]).grid(row=0, column=0, columnspan=2,
                                                  sticky="w", pady=(0, 6))

        # 刷新间隔
        self.row_interval(pad, "刷新间隔", 1)
        # 低电量提醒
        self.row_alert(pad, "低电量提醒", 2)
        # 托盘图标
        self.row_tray(pad, "托盘图标", 3)
        # 开机自启
        self.row_autostart(pad, "开机自启", 4)
        # 诊断
        row = tk.Frame(pad, bg=BG_SOFT)
        row.grid(row=5, column=0, columnspan=2, sticky="w", pady=(10, 0))
        tk.Label(row, text="诊断", bg=BG_SOFT, fg=SUB, font=self.fonts["section"],
                 width=8, anchor="w").pack(side="left")
        Chip(row, "复制诊断信息", lambda _c: self.copy_diagnostics(),
             font=self.fonts["chip"]).pack(side="left", padx=(2, 0))

    def _label(self, parent, text, row):
        tk.Label(parent, text=text, bg=BG_SOFT, fg="#9aa6ba", font=self.fonts["section"],
                 width=8, anchor="w").grid(row=row, column=0, sticky="w", pady=4)

    def row_interval(self, parent, text, row):
        self._label(parent, text, row)
        box = tk.Frame(parent, bg=BG_SOFT)
        box.grid(row=row, column=1, sticky="w", pady=3)
        self.interval_chips = {}
        for sec, label in self.INTERVALS:
            chip = Chip(box, label, lambda c, s=sec: self.set_interval(s),
                        selected=(sec == self.cfg["interval"]), font=self.fonts["chip"])
            chip.pack(side="left", padx=(0, 6))
            self.interval_chips[sec] = chip

    def row_alert(self, parent, text, row):
        self._label(parent, text, row)
        box = tk.Frame(parent, bg=BG_SOFT)
        box.grid(row=row, column=1, sticky="w", pady=3)
        self.alert_chip = Chip(box, "开", lambda _c: self.toggle_alert(),
                               selected=self.cfg["low_alert"], font=self.fonts["chip"])
        self.alert_chip.pack(side="left", padx=(0, 10))
        self.threshold_chips = {}
        for pct in (10, 20, 30):
            chip = Chip(box, "%d%%" % pct, lambda c, p=pct: self.set_threshold(p),
                        selected=(pct == self.cfg["low_threshold"]), font=self.fonts["chip"])
            chip.pack(side="left", padx=(0, 6))
            self.threshold_chips[pct] = chip

    def row_tray(self, parent, text, row):
        self._label(parent, text, row)
        box = tk.Frame(parent, bg=BG_SOFT)
        box.grid(row=row, column=1, sticky="w", pady=3)
        self.tray_chips = {}
        for style, label in (("number", "数字"), ("ring", "电量环")):
            chip = Chip(box, label, lambda c, s=style: self.set_tray_style(s),
                        selected=(style == self.cfg["tray_style"]), font=self.fonts["chip"])
            chip.pack(side="left", padx=(0, 6))
            self.tray_chips[style] = chip

    def row_autostart(self, parent, text, row):
        self._label(parent, text, row)
        box = tk.Frame(parent, bg=BG_SOFT)
        box.grid(row=row, column=1, sticky="w", pady=3)
        self.auto_chip = Chip(box, "开" if self.autostart else "关",
                              lambda _c: self.toggle_autostart(),
                              selected=self.autostart, font=self.fonts["chip"])
        self.auto_chip.pack(side="left")

    def make_button(self, parent, text, command):
        btn = tk.Label(parent, text=text, bg=CHIP, fg=TEXT, font=self.fonts["chip"],
                       padx=12, pady=6, cursor="hand2")
        btn.bind("<Button-1>", lambda _e: command())
        btn.bind("<Enter>", lambda _e: btn.configure(bg="#232b3d"))
        btn.bind("<Leave>", lambda _e: btn.configure(bg=CHIP))
        return btn

    def make_icon_button(self, parent, text, command):
        btn = tk.Label(parent, text=text, bg=BG, fg="#aab4c6", font=(self.fonts["title"][0], 14),
                       padx=8, pady=2, cursor="hand2")
        btn.bind("<Button-1>", lambda _e: command())
        btn.bind("<Enter>", lambda _e: btn.configure(fg=TEXT))
        btn.bind("<Leave>", lambda _e: btn.configure(fg="#aab4c6"))
        return btn

    # -- 设置项 ----------------------------------------------------------
    def interval_label(self):
        for sec, label in self.INTERVALS:
            if sec == self.cfg["interval"]:
                return label
        return "%d 秒" % self.cfg["interval"]

    def set_interval(self, seconds):
        self.cfg["interval"] = seconds
        config.save(self.cfg)
        self.interval_btn.configure(text=self.interval_label())
        for sec, chip in self.interval_chips.items():
            chip.set_selected(sec == seconds)
        self.schedule()

    def cycle_interval(self):
        values = [sec for sec, _ in self.INTERVALS]
        try:
            idx = (values.index(self.cfg["interval"]) + 1) % len(values)
        except ValueError:
            idx = 1
        self.set_interval(values[idx])

    def toggle_alert(self):
        self.cfg["low_alert"] = not self.cfg["low_alert"]
        config.save(self.cfg)
        self.alert_chip.configure(text="开" if self.cfg["low_alert"] else "关")
        self.alert_chip.set_selected(self.cfg["low_alert"])

    def set_threshold(self, pct):
        self.cfg["low_threshold"] = pct
        config.save(self.cfg)
        for p, chip in self.threshold_chips.items():
            chip.set_selected(p == pct)
        self.alerted.clear()

    def set_tray_style(self, style):
        self.cfg["tray_style"] = style
        config.save(self.cfg)
        for s, chip in self.tray_chips.items():
            chip.set_selected(s == style)
        self.push_tray_from_cards()

    def push_tray_from_cards(self):
        results = [(cls, self.cards[cls].reading) for cls in self.order
                   if self.cards[cls].reading is not None]
        if results:
            self.push_tray(results)

    def toggle_autostart(self):
        target = not self.autostart
        win_shell.set_autostart(target)
        self.autostart = win_shell.autostart_enabled()
        self.auto_chip.configure(text="开" if self.autostart else "关")
        self.auto_chip.set_selected(self.autostart)

    def toggle_settings(self):
        if self.settings_open:
            self.settings.pack_forget()
            self.settings_open = False
            self.gear.configure(fg=SUB)
        else:
            self.settings.pack(fill="x", padx=22, pady=(2, 8), before=self.bottom)
            self.settings_open = True
            self.gear.configure(fg=ACCENT)
        self.root.update_idletasks()
        self.resize_to_content()

    def resize_to_content(self):
        """按内容实际高度调整窗口，收起/展开设置时不留下空白。"""
        try:
            geo = self.root.geometry()
            parts = geo.split("+")
            x, y = parts[1], parts[2]
        except (IndexError, ValueError):
            return
        h = max(400, self.root.winfo_reqheight() + 12)
        self.root.geometry("%dx%d+%s+%s" % (W, h, x, y))

    def copy_diagnostics(self):
        lines = ["设备电量 诊断信息", "时间: " + time.strftime("%Y-%m-%d %H:%M:%S"),
                 "系统: " + win_shell.sys.platform + " " + str(win_shell.sys.getwindowsversion()),
                 ""]
        for cls in self.order:
            card = self.cards.get(cls)
            r = card.reading if card else None
            if r is None:
                lines.append("%s: 尚未读取" % cls.NAME)
            elif r.ok:
                lines.append("%s: %d%% 模式=%s 充电=%s" % (cls.NAME, r.level, r.mode or "-",
                                                          r.charging))
                lines.append("    来源: %s" % r.source)
                if r.note:
                    lines.append("    备注: %s" % r.note)
            else:
                lines.append("%s: 读取失败 (%s)" % (cls.NAME, r.error))
        text = "\n".join(lines)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status.configure(text="诊断信息已复制到剪贴板")

    # -- 托盘 ------------------------------------------------------------
    def start_tray(self):
        self.tray = tray_mod.Tray(
            on_open=lambda: self.actions.put("open"),
            on_refresh=lambda: self.actions.put("refresh"),
            on_exit=lambda: self.actions.put("exit"),
            is_autostart=lambda: self.autostart,
            on_toggle_autostart=lambda: self.actions.put("autostart"),
            is_alert=lambda: self.cfg["low_alert"],
            on_toggle_alert=lambda: self.actions.put("alert"),
            style_getter=lambda: self.cfg["tray_style"],
        )
        self.tray.start()
        self.push_tray([])

    def push_tray(self, results):
        rows = []
        for cls, r in results:
            if r.ok:
                tip = "%s %d%%（%s）" % (cls.NAME, r.level, r.mode or "-")
                if r.charging:
                    tip += " · 充电中"
            else:
                tip = "%s %s" % (cls.NAME, r.short_error)
            rows.append({
                "key": cls.SHORT,
                "level": r.level if r.ok else None,
                "tip": tip,
                "plate": cls.KIND == "键盘",
            })
        self.tray.update(rows)

    # -- 读取 ------------------------------------------------------------
    def refresh(self):
        if self.busy:
            return
        self.busy = True
        self.status.configure(text="正在读取…")
        threading.Thread(target=self._work, daemon=True).start()
        self.root.after(80, self.pump_reads)

    def _work(self):
        try:
            self.job.run(self.order)
        finally:
            self.busy = False

    def pump_reads(self):
        try:
            while True:
                item = self.q.get_nowait()
                if item[0] == "device":
                    _, cls, reading = item
                    card = self.cards.get(cls)
                    if card:
                        card.update(reading, time.strftime("%H:%M:%S"))
                elif item[0] == "done":
                    _, results, when = item
                    ok = sum(1 for _c, r in results if r.ok)
                    self.status.configure(
                        text="%d/%d 台设备读到电量 · 更新于 %s" % (
                            ok, len(results), time.strftime("%H:%M:%S", time.localtime(when))))
                    self.push_tray(results)
                    self.check_low_battery(results)
                    return
        except queue.Empty:
            pass
        self.root.after(80, self.pump_reads)

    def check_low_battery(self, results):
        if not self.cfg["low_alert"]:
            return
        threshold = self.cfg["low_threshold"]
        for cls, r in results:
            if not r.ok or r.charging:
                continue
            key = cls.SHORT
            if r.level <= threshold and not self.alerted.get(key):
                self.alerted[key] = True
                self.tray.balloon("%s 电量低" % cls.NAME,
                                  "剩余 %d%%，记得充电。" % r.level, warning=True)
            elif r.level > threshold + 3:
                self.alerted[key] = False

    def schedule(self):
        if getattr(self, "after_id", None):
            self.root.after_cancel(self.after_id)
        self.after_id = self.root.after(self.cfg["interval"] * 1000, self._tick)

    def _tick(self):
        self.refresh()
        self.schedule()

    def tick_animation(self):
        need = False
        for card in self.cards.values():
            if card.animate():
                need = True
        self.root.after(30 if need else 120, self.tick_animation)

    # -- 托盘动作 --------------------------------------------------------
    def pump(self):
        try:
            while True:
                action = self.actions.get_nowait()
                if action == "open":
                    self.show_panel()
                elif action == "refresh":
                    self.refresh()
                elif action == "autostart":
                    self.toggle_autostart()
                elif action == "alert":
                    self.toggle_alert()
                elif action == "exit":
                    self.quit()
                    return
        except queue.Empty:
            pass
        self.root.after(150, self.pump)

    def show_panel(self):
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(400, lambda: self.root.attributes("-topmost", False))
        self.root.focus_force()

    def hide_to_tray(self):
        self.root.withdraw()

    def quit(self):
        try:
            self.tray.stop()
        except Exception:
            pass
        try:
            import win_icon
            win_icon.destroy_all()
        except Exception:
            pass
        self.root.destroy()


def already_running():
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if kernel32.GetLastError() != 183:
        return False

    user32 = ctypes.WinDLL("user32")
    user32.FindWindowW.restype = ctypes.c_void_p
    user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
    user32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                    ctypes.c_size_t, ctypes.c_ssize_t]
    user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]

    tray_hwnd = user32.FindWindowW("DeviceBatteryTrayWnd", None)
    if tray_hwnd:
        user32.PostMessageW(tray_hwnd, 0x0400 + 1, 0, 0x0202)
        return True

    hwnd = user32.FindWindowW(None, WINDOW_TITLE)
    if hwnd:
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
    return True


def run_once():
    results = []
    for cls in devices.ALL_DEVICES:
        r = cls.read()
        results.append((cls, r))
        if r.ok:
            extra = [r.mode] if r.mode else []
            if r.charging:
                extra.append("充电中")
            print("%-12s %3d%%   %s" % (cls.NAME, r.level, " ".join(extra)))
        else:
            hint = ("（%s）" % r.retries_hint) if r.retries_hint else ""
            print("%-12s  --    %s%s" % (cls.NAME, r.error, hint))
    return 0 if any(r.ok for _c, r in results) else 1


def main():
    parser = argparse.ArgumentParser(description="显示 2.4G 外设电量")
    parser.add_argument("--once", action="store_true", help="读一次并打印到控制台后退出")
    parser.add_argument("--tray", action="store_true", help="启动后只显示托盘，不弹面板")
    parser.add_argument("--debug", action="store_true", help="打印调试信息")
    args = parser.parse_args()

    if args.once:
        raise SystemExit(run_once())

    if already_running():
        return

    root = tk.Tk()
    App(root, start_hidden=args.tray or config.load().get("start_minimized", False))
    root.mainloop()


if __name__ == "__main__":
    main()
