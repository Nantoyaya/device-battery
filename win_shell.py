# -*- coding: utf-8 -*-
"""win_shell.py —— 启动文件夹、开机自启快捷方式（纯 ctypes COM，不依赖 pywin32）。

开机自启用「启动」文件夹里的 .lnk（任务管理器 →「启动」里能直接看到、能启用/禁用），
不用注册表 Run。创建/读取 .lnk 全部走 IShellLinkW + IPersistFile。
"""

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_SCRIPT = os.path.join(BASE_DIR, "app.py")
LNK_NAME = "设备电量.lnk"

CLSID_ShellLink = "{00021401-0000-0000-C000-000000000046}"
IID_IShellLinkW = "{000214F9-0000-0000-C000-000000000046}"
IID_IPersistFile = "{0000010B-0000-0000-C000-000000000046}"

CLSCTX_INPROC_SERVER = 0x1
CSIDL_STARTUP = 0x07
STARTUP_APPROVED = (r"Software\Microsoft\Windows\CurrentVersion"
                    r"\Explorer\StartupApproved\StartupFolder")


class GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16),
                ("Data3", ctypes.c_uint16), ("Data4", ctypes.c_ubyte * 8)]


class WIN32_FIND_DATAW(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", wintypes.DWORD),
        ("ftCreationTime", wintypes.FILETIME),
        ("ftLastAccessTime", wintypes.FILETIME),
        ("ftLastWriteTime", wintypes.FILETIME),
        ("nFileSizeHigh", wintypes.DWORD),
        ("nFileSizeLow", wintypes.DWORD),
        ("dwReserved0", wintypes.DWORD),
        ("dwReserved1", wintypes.DWORD),
        ("cFileName", wintypes.WCHAR * 260),
        ("cAlternateFileName", wintypes.WCHAR * 14),
    ]


ole32 = ctypes.WinDLL("ole32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)

ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
ole32.CoInitializeEx.restype = ctypes.c_long
ole32.CoCreateInstance.argtypes = [ctypes.POINTER(GUID), ctypes.c_void_p, ctypes.c_ulong,
                                   ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)]
ole32.CoCreateInstance.restype = ctypes.c_long
ole32.CLSIDFromString.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(GUID)]
ole32.CLSIDFromString.restype = ctypes.c_long
shell32.SHGetFolderPathW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p,
                                     ctypes.c_uint32, ctypes.c_wchar_p]
shell32.SHGetFolderPathW.restype = ctypes.c_long


def _guid(text):
    g = GUID()
    ole32.CLSIDFromString(ctypes.c_wchar_p(text), ctypes.byref(g))
    return g


def _com_init():
    ole32.CoInitializeEx(None, 0x2)  # COINIT_APARTMENTTHREADED


def _vtbl(obj, index, restype, argtypes):
    vtable = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
    proto = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
    return proto(vtable[index])


def startup_dir():
    buf = ctypes.create_unicode_buffer(260)
    if shell32.SHGetFolderPathW(None, CSIDL_STARTUP, None, 0, buf) == 0:
        return buf.value
    return os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup")


def pythonw_path():
    exe = sys.executable or ""
    cand = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return cand if os.path.exists(cand) else exe


def lnk_path():
    return os.path.join(startup_dir(), LNK_NAME)


def icon_path():
    return os.path.join(BASE_DIR, "docs", "battery.ico")


def create_shortcut(dest, target, arguments="", workdir="", icon="", description=""):
    """创建 .lnk，返回是否成功。"""
    _com_init()
    punk = ctypes.c_void_p()
    hr = ole32.CoCreateInstance(ctypes.byref(_guid(CLSID_ShellLink)), None,
                                CLSCTX_INPROC_SERVER,
                                ctypes.byref(_guid(IID_IShellLinkW)), ctypes.byref(punk))
    if hr != 0 or not punk:
        return False
    try:
        SetPath = _vtbl(punk, 20, ctypes.c_long, [ctypes.c_wchar_p])
        SetArguments = _vtbl(punk, 11, ctypes.c_long, [ctypes.c_wchar_p])
        SetWorkDir = _vtbl(punk, 9, ctypes.c_long, [ctypes.c_wchar_p])
        SetDescription = _vtbl(punk, 7, ctypes.c_long, [ctypes.c_wchar_p])
        SetIconLocation = _vtbl(punk, 17, ctypes.c_long, [ctypes.c_wchar_p, ctypes.c_int])
        QueryInterface = _vtbl(punk, 0, ctypes.c_long,
                               [ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)])

        SetPath(punk, target)
        if arguments:
            SetArguments(punk, arguments)
        if workdir:
            SetWorkDir(punk, workdir)
        if description:
            SetDescription(punk, description)
        if icon:
            SetIconLocation(punk, icon, 0)

        persist = ctypes.c_void_p()
        if QueryInterface(punk, ctypes.byref(_guid(IID_IPersistFile)),
                          ctypes.byref(persist)) != 0 or not persist:
            return False
        try:
            Save = _vtbl(persist, 6, ctypes.c_long, [ctypes.c_wchar_p, ctypes.c_bool])
            return Save(persist, dest, True) == 0
        finally:
            _release(persist)
    finally:
        _release(punk)


def _release(obj):
    try:
        Release = _vtbl(obj, 2, ctypes.c_ulong, [])
        Release(obj)
    except Exception:
        pass


def read_shortcut(dest):
    """读取 .lnk 的目标与参数；失败返回 (None, None)。"""
    if not os.path.exists(dest):
        return None, None
    _com_init()
    punk = ctypes.c_void_p()
    hr = ole32.CoCreateInstance(ctypes.byref(_guid(CLSID_ShellLink)), None,
                                CLSCTX_INPROC_SERVER,
                                ctypes.byref(_guid(IID_IShellLinkW)), ctypes.byref(punk))
    if hr != 0 or not punk:
        return None, None
    try:
        QueryInterface = _vtbl(punk, 0, ctypes.c_long,
                               [ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)])
        persist = ctypes.c_void_p()
        if QueryInterface(punk, ctypes.byref(_guid(IID_IPersistFile)),
                          ctypes.byref(persist)) != 0 or not persist:
            return None, None
        try:
            Load = _vtbl(persist, 5, ctypes.c_long, [ctypes.c_wchar_p, wintypes.DWORD])
            if Load(persist, dest, 0) != 0:
                return None, None
            GetPath = _vtbl(punk, 3, ctypes.c_long,
                            [ctypes.c_wchar_p, ctypes.c_int,
                             ctypes.POINTER(WIN32_FIND_DATAW), wintypes.DWORD])
            GetArguments = _vtbl(punk, 10, ctypes.c_long, [ctypes.c_wchar_p, ctypes.c_int])

            buf = ctypes.create_unicode_buffer(520)
            data = WIN32_FIND_DATAW()
            GetPath(punk, buf, 520, ctypes.byref(data), 0)
            abuf = ctypes.create_unicode_buffer(520)
            GetArguments(punk, abuf, 520)
            return buf.value, abuf.value
        finally:
            _release(persist)
    finally:
        _release(punk)


def _startup_disabled():
    """任务管理器里被禁用过？(StartupApproved 首字节 0x03 = 禁用)"""
    import winreg
    base = os.path.basename(lnk_path())
    names = (base, os.path.splitext(base)[0])
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_APPROVED, 0, winreg.KEY_READ) as k:
            for name in names:
                try:
                    data, _ = winreg.QueryValueEx(k, name)
                except OSError:
                    continue
                if isinstance(data, (bytes, bytearray)) and data:
                    return data[0] == 0x03
    except OSError:
        pass
    return False


def autostart_enabled():
    """真实的自启状态：快捷方式存在、指向本项目的 app.py，且没被任务管理器禁用。"""
    dest = lnk_path()
    if not os.path.exists(dest):
        return False
    target, args = read_shortcut(dest)
    if not target:
        return False
    if "pythonw" not in target.lower() and "python" not in target.lower():
        return False
    if APP_SCRIPT.lower() not in (args or "").lower():
        return False
    return not _startup_disabled()


def enable_autostart():
    dest = lnk_path()
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    ok = create_shortcut(
        dest,
        pythonw_path(),
        '"%s" --tray' % APP_SCRIPT,
        BASE_DIR,
        icon_path() if os.path.exists(icon_path()) else "",
        "设备电量（开机后台常驻，托盘显示电量）",
    )
    if ok:
        _clear_disabled_flag()
    return ok


def disable_autostart():
    try:
        if os.path.exists(lnk_path()):
            os.remove(lnk_path())
        return True
    except OSError:
        return False


def _clear_disabled_flag():
    """把任务管理器里的“已禁用”记录清掉，避免刚建好就显示禁用。"""
    import winreg
    base = os.path.basename(lnk_path())
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_APPROVED, 0,
                            winreg.KEY_SET_VALUE) as k:
            for name in (base, os.path.splitext(base)[0]):
                try:
                    winreg.DeleteValue(k, name)
                except OSError:
                    pass
    except OSError:
        pass


def set_autostart(enabled):
    return enable_autostart() if enabled else disable_autostart()


if __name__ == "__main__":
    print("startup dir:", startup_dir())
    print("lnk       :", lnk_path())
    print("enabled   :", autostart_enabled())
    print("target    :", read_shortcut(lnk_path()))
