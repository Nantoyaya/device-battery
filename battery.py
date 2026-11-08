# -*- coding: utf-8 -*-
"""battery.py —— 只在后台线程里跑的读取调度。

界面线程绝不直接碰 HID：所有读取都丢进队列，结果通过 queue.Queue 回主线程。
"""

from __future__ import annotations

import queue
import time
import traceback

import devices


class ReadingJob:
    """一轮读取：读三台设备，把结果按设备顺序塞进队列。"""

    def __init__(self, out_queue: "queue.Queue"):
        self.q = out_queue

    def run(self, order=None):
        classes = order or devices.ALL_DEVICES
        results = []
        for cls in classes:
            started = time.monotonic()
            try:
                r = cls.read()
            except Exception:                                  # noqa: BLE001 - 任何异常都不能弄死界面
                r = devices.Reading(error="读取异常", note=traceback.format_exc(limit=1))
            r.note = r.note or ""
            r.elapsed = time.monotonic() - started
            results.append((cls, r))
            self.q.put(("device", cls, r))
        self.q.put(("done", results, time.time()))
