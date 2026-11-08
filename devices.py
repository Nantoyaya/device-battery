# -*- coding: utf-8 -*-
"""devices.py —— 两台设备的识别与电量读取协议。

每台设备一个类：``match()`` 找到自己的 HID 接口，``read()`` 返回一个 Reading。

协议来源：
  * AULA SC360SE  —— 官方驱动 config.xml / mouse_sc360se.xml + 实测抓包
                     请求 [08 10 00 ...]，回复 [00 10 00 01 0B 'S057' 85 01 25 01 00 <电量> <供电标志> ...]
  * 凌豹 K98      —— 实测：Output Report 0x13，命令 0x4A，回复第 5 字节为电量，
                     第 6 字节为状态，最后一字节为前 19 字节累加和
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import hid_win
from hid_win import HidDevice


# --------------------------------------------------------------------------
# 通用工具
# --------------------------------------------------------------------------

def find_interfaces(vid, pid, usage_page=None, usage=None):
    out = []
    for d in hid_win.enumerate_hid():
        if d.vid != vid or d.pid != pid:
            continue
        if usage_page is not None and d.usage_page != usage_page:
            continue
        if usage is not None and d.usage != usage:
            continue
        out.append(d)
    return out


def wait_reply(dev, cmd, timeout=1.6, cmd_index=1):
    """等待一条 byte[cmd_index] == cmd 的报告，返回原始 bytes。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = dev.read_input(80)
        if not r:
            continue
        if len(r) > cmd_index and r[cmd_index] == cmd:
            return bytes(r)
    return None


@dataclass
class Reading:
    level: Optional[int] = None          # 0-100
    charging: Optional[bool] = None
    mode: str = ""                       # "2.4G" / "USB" / ""
    source: str = ""                     # 数据来源说明
    note: str = ""                       # 附加信息
    error: str = ""                      # 非空表示这次没读到
    retries_hint: str = ""               # 给用户的提示（如"动一下鼠标"）
    elapsed: float = 0.0

    @property
    def ok(self) -> bool:
        return self.level is not None and not self.error

    @property
    def short_error(self) -> str:
        return self.error or "未读到"


# --------------------------------------------------------------------------
# AULA SC360SE（狼蛛 SC360se）
# --------------------------------------------------------------------------

class AulaSC360SE:
    NAME = "狼蛛 SC360se"
    SHORT = "SC360se"
    KIND = "鼠标"

    VID_WIRELESS, PID_WIRELESS = 0x249A, 0x5C2F
    VID_WIRED, PID_WIRED = 0x248A, 0x5D2E
    USAGE_PAGE, USAGE = 0xFF01, 0x0010
    REPORT_LEN = 33
    CMD_INFO = 0x10
    LEVEL_OFFSET = 14
    POWER_OFFSET = 15

    @classmethod
    def match(cls):
        for vid, pid, mode in ((cls.VID_WIRELESS, cls.PID_WIRELESS, "2.4G"),
                               (cls.VID_WIRED, cls.PID_WIRED, "USB")):
            cands = find_interfaces(vid, pid, cls.USAGE_PAGE, cls.USAGE)
            if cands:
                return cands[0], mode
        return None, None

    @classmethod
    def read(cls, attempts: int = 3) -> Reading:
        iface, mode = cls.match()
        if iface is None:
            return Reading(error="未检测到接收器", retries_hint="插好 2.4G 接收器")
        try:
            with HidDevice(iface) as dev:
                dev.drain_input(20)
                reply = None
                for _ in range(attempts):
                    buf = bytearray(cls.REPORT_LEN)
                    buf[0] = 0x08
                    buf[1] = cls.CMD_INFO
                    dev.write_output(bytes(buf))
                    reply = wait_reply(dev, cls.CMD_INFO, timeout=1.4)
                    if reply:
                        break
                if not reply:
                    return Reading(error="鼠标没有应答", retries_hint="动一下鼠标把它唤醒后重试")
                if len(reply) <= cls.LEVEL_OFFSET:
                    return Reading(error="回复长度异常")
                level = reply[cls.LEVEL_OFFSET]
                powered = (len(reply) > cls.POWER_OFFSET and reply[cls.POWER_OFFSET] == 0)
                dev_name = ""
                try:
                    dev_name = reply[5:9].decode("ascii", "ignore").strip("\x00 ")
                except Exception:
                    pass
                return Reading(
                    level=level if 0 <= level <= 100 else None,
                    charging=True if mode == "USB" else (True if powered else None),
                    mode=mode,
                    source="厂商协议 0x10 · 回复第 14 字节",
                    note=("设备号 %s · " % dev_name if dev_name else "") + "接口 0xFF01",
                )
        except OSError as exc:
            return Reading(error="打开 HID 接口失败", note=str(exc))


# --------------------------------------------------------------------------
# 凌豹 K98（三模键盘）
# --------------------------------------------------------------------------

def _sum_checksum(data: bytes) -> int:
    return sum(data) & 0xFF


class LingbaoK98:
    NAME = "凌豹 K98"
    SHORT = "K98"
    KIND = "键盘"

    VID, PID = 0x3554, 0xFA09
    USAGE_PAGE, USAGE = 0xFF02, 0x0002
    REPORT_LEN = 20
    REPORT_ID = 0x13
    CMD_BATTERY = 0x4A
    LEVEL_OFFSET = 5
    FLAG_OFFSET = 6

    @classmethod
    def match(cls):
        cands = find_interfaces(cls.VID, cls.PID, cls.USAGE_PAGE, cls.USAGE)
        return cands[0] if cands else None

    @classmethod
    def _touch_status(cls):
        """读一下 0x06 状态寄存器再原值写回：能一定程度上把休眠的键盘捅醒。"""
        try:
            f = find_interfaces(cls.VID, cls.PID, 0xFF04, 0x0002)
            if not f:
                return False
            with HidDevice(f[0]) as dev:
                rep = dev.get_feature(0x06, 8)
                if rep:
                    return dev.set_feature(rep)
        except Exception:                                      # noqa: BLE001
            return False
        return False

    @classmethod
    def read(cls, attempts: int = 3) -> Reading:
        iface = cls.match()
        if iface is None:
            return Reading(error="未检测到接收器", retries_hint="插好 2.4G 接收器")
        try:
            with HidDevice(iface) as dev:
                dev.drain_input(20)
                reply = None
                for i in range(attempts):
                    if i:
                        cls._touch_status()
                    buf = bytearray(cls.REPORT_LEN)
                    buf[0] = cls.REPORT_ID
                    buf[1] = cls.CMD_BATTERY
                    dev.write_output(bytes(buf))
                    reply = wait_reply(dev, cls.CMD_BATTERY, timeout=1.2)
                    if reply:
                        break
                if not reply:
                    return Reading(error="键盘休眠中", retries_hint="敲一下键盘任意键再刷新")
                if len(reply) < 19:
                    return Reading(error="回复长度异常")

                payload_len = reply[4]
                level = reply[cls.LEVEL_OFFSET]
                flag = reply[cls.FLAG_OFFSET]
                crc_ok = (len(reply) >= 20 and _sum_checksum(reply[:19]) == reply[19])

                if payload_len != 2 or not (0 <= level <= 100):
                    return Reading(error="回复内容不符合预期", note=reply.hex(" "))

                return Reading(
                    level=level,
                    charging=None,
                    mode="2.4G",
                    source="厂商协议 0x4A · 回复第 5 字节",
                    note="校验%s · 状态 0x%02X" % ("通过" if crc_ok else "失败", flag),
                )
        except OSError as exc:
            return Reading(error="打开 HID 接口失败", note=str(exc))


# --------------------------------------------------------------------------
ALL_DEVICES = [AulaSC360SE, LingbaoK98]
