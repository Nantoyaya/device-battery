"""tray_selftest.py —— 验证托盘图标能否成功注册（打印 Shell_NotifyIconW 的返回）。"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tray as tray_mod


def main():
    t = tray_mod.Tray(on_open=lambda: print("open"), on_refresh=lambda: print("refresh"),
                      on_exit=lambda: print("exit"), is_autostart=lambda: True)
    t.start()
    print("hwnd:", t.hwnd)
    t.update([
        {"key": "mouse", "level": 95, "tip": "狼蛛 SC360se 95%", "plate": False},
        {"key": "kb", "level": 100, "tip": "凌豹 K98 100%", "plate": True},
    ])
    time.sleep(2.0)
    print("ids:", t._ids)
    print("hicons:", t._hicons)
    print("notify results:", t.last_results)
    t.stop()
    print("stopped")


main()
