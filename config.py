# -*- coding: utf-8 -*-
"""config.py —— 设置持久化（只存设置，不存设备数据、不写日志）。

放在 %APPDATA%\\DeviceBattery\\config.json，卸载时删目录即可。
"""

from __future__ import annotations

import json
import os

APPDATA = os.environ.get("APPDATA") or os.path.expanduser("~")
DIR = os.path.join(APPDATA, "DeviceBattery")
PATH = os.path.join(DIR, "config.json")

DEFAULTS = {
    "interval": 60,          # 刷新间隔（秒）
    "low_alert": True,       # 低电量提醒
    "low_threshold": 20,     # 低电量阈值（%）
    "tray_style": "number",  # number = 数字图标 / ring = 电量环
    "start_minimized": False,  # 开机自启时是否只显示托盘
}


def load() -> dict:
    cfg = dict(DEFAULTS)
    try:
        with open(PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for k in DEFAULTS:
                if k in data and isinstance(data[k], type(DEFAULTS[k])):
                    cfg[k] = data[k]
            for k in ("low_threshold",):
                cfg[k] = max(5, min(90, int(cfg[k])))
            cfg["interval"] = max(10, min(3600, int(cfg["interval"])))
            if cfg["tray_style"] not in ("number", "ring"):
                cfg["tray_style"] = DEFAULTS["tray_style"]
    except (OSError, ValueError):
        pass
    return cfg


def save(cfg: dict) -> None:
    try:
        os.makedirs(DIR, exist_ok=True)
        clean = {k: cfg.get(k, DEFAULTS[k]) for k in DEFAULTS}
        with open(PATH, "w", encoding="utf-8") as f:
            json.dump(clean, f, ensure_ascii=False, indent=2)
    except OSError:
        pass
