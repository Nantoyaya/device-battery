# -*- coding: utf-8 -*-
"""tray.py —— 通知区域（托盘）常驻图标，纯 ctypes 调 Shell_NotifyIconW。

每台设备一个图标，图标上的数字就是电量；右键出菜单，左键打开面板。
托盘跑在自己的线程里，界面线程只往这儿丢状态、通过回调把用户操作排进队列。
"""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes

import win_icon

user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_COMMAND = 0x0111
WM_NULL = 0x0000
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
WM_LBUTTONDBLCLK = 0x0203
WM_CONTEXTMENU = 0x007B

WM_TRAY = 0x0400 + 1        # WM_APP + 1 回调消息
WM_TRAY_UPDATE = 0x0400 + 2

NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 0x01, 0x02, 0x04, 0x10
NIIF_INFO, NIIF_WARNING, NIIF_ERROR = 0x1, 0x2, 0x3

MF_STRING, MF_SEPARATOR, MF_CHECKED, MF_UNCHECKED = 0x0000, 0x0800, 0x0008, 0x0000
TPM_RIGHTBUTTON = 0x0002
TPM_RETURNCMD = 0x0100

ID_OPEN, ID_REFRESH, ID_AUTOSTART, ID_EXIT, ID_ALERT = 1001, 1002, 1003, 1004, 1005

HWND_MESSAGE = ctypes.c_void_p(-3)


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", ctypes.c_byte * 16),
        ("hBalloonIcon", wintypes.HICON),
    ]


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", ctypes.c_void_p),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HICON),
    ]


WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
                             ctypes.c_size_t, ctypes.c_ssize_t)

user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
user32.RegisterClassExW.restype = wintypes.WORD
user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                   wintypes.DWORD, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, wintypes.HWND,
                                   wintypes.HMENU, wintypes.HINSTANCE, ctypes.c_void_p]
user32.CreateWindowExW.restype = wintypes.HWND
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t]
user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = ctypes.c_int
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.restype = ctypes.c_ssize_t
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t]
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.CreatePopupMenu.restype = wintypes.HMENU
user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
user32.TrackPopupMenu.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int,
                                  ctypes.c_int, wintypes.HWND, ctypes.c_void_p]
user32.TrackPopupMenu.restype = ctypes.c_int
user32.DestroyMenu.argtypes = [wintypes.HMENU]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE

shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
shell32.Shell_NotifyIconW.restype = wintypes.BOOL


class Tray:
    """托盘图标。rows 形如 [{'key':'mouse','title':'狼蛛 SC360se','level':95,'tip':'...','plate':False}]"""

    def __init__(self, on_open=None, on_refresh=None, on_exit=None,
                 is_autostart=None, on_toggle_autostart=None,
                 is_alert=None, on_toggle_alert=None, style_getter=None):
        self.on_open = on_open or (lambda: None)
        self.on_refresh = on_refresh or (lambda: None)
        self.on_exit = on_exit or (lambda: None)
        self.is_autostart = is_autostart or (lambda: False)
        self.on_toggle_autostart = on_toggle_autostart or (lambda: None)
        self.is_alert = is_alert or (lambda: True)
        self.on_toggle_alert = on_toggle_alert or (lambda: None)
        self.style_getter = style_getter or (lambda: "number")

        self.hwnd = None
        self._thread = None
        self._rows = []
        self._lock = threading.Lock()
        self._class_name = "DeviceBatteryTrayWnd"
        self._ids = {}
        self._hicons = {}
        self._proc = None
        self._ready = threading.Event()
        self.last_results = []

    # -- 外部接口 --------------------------------------------------------
    def start(self):
        self._thread = threading.Thread(target=self._run, name="tray", daemon=True)
        self._thread.start()
        self._ready.wait(3.0)

    def update(self, rows):
        with self._lock:
            self._rows = list(rows)
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_TRAY_UPDATE, 0, 0)

    def show(self):
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_TRAY_UPDATE, 0, 0)

    def balloon(self, title, text, warning=True):
        """弹一个系统通知（气泡）。只能在托盘线程之外调用。"""
        with self._lock:
            rows = list(self._rows)
        if not rows or not self.hwnd:
            return
        key = rows[0].get("key")
        uid = self._ids.get(key)
        if not uid:
            return
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = uid
        nid.uFlags = NIF_INFO
        nid.uVersion = 0
        nid.szInfoTitle = title[:63]
        nid.szInfo = text[:255]
        nid.dwInfoFlags = NIIF_WARNING if warning else NIIF_INFO
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))

    def stop(self):
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)
        if self._thread:
            self._thread.join(2.0)

    # -- 线程内部 --------------------------------------------------------
    def _run(self):
        hinst = kernel32.GetModuleHandleW(None)
        self._proc = WNDPROC(self._wndproc)

        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = ctypes.cast(self._proc, ctypes.c_void_p)
        wc.hInstance = hinst
        wc.lpszClassName = self._class_name
        user32.RegisterClassExW(ctypes.byref(wc))

        self.hwnd = user32.CreateWindowExW(0, self._class_name, "设备电量托盘",
                                           0, 0, 0, 0, 0, None, None, hinst, None)
        if not self.hwnd:
            self._ready.set()
            return

        self._rebuild_icons()
        self._ready.set()

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def _rebuild_icons(self):
        with self._lock:
            rows = list(self._rows)

        # 按 key 分配固定 uID，避免图标顺序乱跳
        for row in rows:
            key = row.get("key") or row.get("title")
            if key not in self._ids:
                self._ids[key] = len(self._ids) + 1

        for row in rows:
            key = row.get("key") or row.get("title")
            uid = self._ids[key]
            level = row.get("level")
            style = self.style_getter()
            if level is None:
                text, color = "-", (150, 158, 170)
            else:
                text, color = str(level), _level_color(level)
            if style == "ring" and level is not None:
                hicon = win_icon.make_ring_hicon(level, color)
            else:
                hicon = win_icon.make_hicon(text, color, row.get("plate", False))

            nid = NOTIFYICONDATAW()
            nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
            nid.hWnd = self.hwnd
            nid.uID = uid
            nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
            nid.uCallbackMessage = WM_TRAY
            nid.hIcon = hicon
            tip = row.get("tip") or ""
            nid.szTip = tip[:127]

            old = self._hicons.get(key)
            action = NIM_ADD if old is None else NIM_MODIFY
            ok = bool(shell32.Shell_NotifyIconW(action, ctypes.byref(nid)))
            if not ok:
                # 再试一次 ADD，防止外壳重启过
                ok = bool(shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)))
            self.last_results.append((key, action, ok))
            self._hicons[key] = hicon

        # 多余的（设备变少）删掉
        alive = set(self._ids[k] for k in [r.get("key") or r.get("title") for r in rows])
        for key, uid in list(self._ids.items()):
            if uid not in alive:
                nid = NOTIFYICONDATAW()
                nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
                nid.hWnd = self.hwnd
                nid.uID = uid
                shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
                del self._ids[key]
                self._hicons.pop(key, None)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_TRAY:
            event = lparam & 0xFFFF
            if event in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                self.on_open()
            elif event in (WM_RBUTTONUP, WM_CONTEXTMENU):
                self._popup(hwnd)
            return 0
        if msg == WM_TRAY_UPDATE:
            self._rebuild_icons()
            return 0
        if msg == WM_COMMAND:
            cmd = wparam & 0xFFFF
            if cmd == ID_OPEN:
                self.on_open()
            elif cmd == ID_REFRESH:
                self.on_refresh()
            elif cmd == ID_AUTOSTART:
                self.on_toggle_autostart()
            elif cmd == ID_ALERT:
                self.on_toggle_alert()
            elif cmd == ID_EXIT:
                self.on_exit()
            return 0
        if msg == WM_CLOSE:
            self._remove_all()
            user32.DestroyWindow(hwnd)
            user32.PostQuitMessage(0)      # 必须发，否则留僵尸线程
            return 0
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _remove_all(self):
        for uid in list(self._ids.values()):
            nid = NOTIFYICONDATAW()
            nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
            nid.hWnd = self.hwnd
            nid.uID = uid
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
        self._ids.clear()

    def _popup(self, hwnd):
        menu = user32.CreatePopupMenu()
        user32.AppendMenuW(menu, MF_STRING, ID_OPEN, "打开面板")
        user32.AppendMenuW(menu, MF_STRING, ID_REFRESH, "立即刷新")
        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        alert_flag = MF_CHECKED if self.is_alert() else MF_UNCHECKED
        user32.AppendMenuW(menu, MF_STRING | alert_flag, ID_ALERT, "低电量提醒")
        auto_flag = MF_CHECKED if self.is_autostart() else MF_UNCHECKED
        user32.AppendMenuW(menu, MF_STRING | auto_flag, ID_AUTOSTART, "开机自启")
        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, MF_STRING, ID_EXIT, "退出")

        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(hwnd)
        choice = user32.TrackPopupMenu(menu, TPM_RIGHTBUTTON | TPM_RETURNCMD,
                                       pt.x, pt.y, 0, hwnd, None)
        user32.PostMessageW(hwnd, WM_NULL, 0, 0)
        user32.DestroyMenu(menu)
        if choice:
            user32.PostMessageW(hwnd, WM_COMMAND, choice, 0)


def _level_color(level):
    if level >= 60:
        return (61, 220, 132)
    if level >= 30:
        return (255, 176, 32)
    return (255, 93, 93)
