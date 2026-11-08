"""Minimal HID layer for Windows, pure ctypes (no hidapi).

Only what this project needs:
  * enumerate HID interfaces with parsed caps (usage page/usage, report lengths)
  * read the raw report descriptor
  * synchronous Feature report get/set
  * Output report write + overlapped Input report read with timeout
"""

import ctypes
import ctypes.wintypes as w
import time

HIDDLL = ctypes.WinDLL("hid.dll")
K32 = ctypes.WinDLL("kernel32.dll", use_last_error=True)
SETUPAPI = ctypes.WinDLL("setupapi.dll", use_last_error=True)

INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x1
FILE_SHARE_WRITE = 0x2
OPEN_EXISTING = 3
FILE_FLAG_OVERLAPPED = 0x40000000

DIGCF_PRESENT = 0x2
DIGCF_DEVICEINTERFACE = 0x10

HID_GUID = "{4d1e55b2-f16f-11cf-88cb-001111000030}"
IOCTL_HID_GET_REPORT_DESCRIPTOR = 0x000B0000


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def from_string(cls, s):
        g = cls()
        ctypes.windll.ole32.CLSIDFromString(ctypes.c_wchar_p(s), ctypes.byref(g))
        return g


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint32),
        ("InterfaceClassGuid", GUID),
        ("Flags", ctypes.c_uint32),
        ("Reserved", ctypes.c_void_p),
    ]


class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Size", ctypes.c_uint32),
        ("VendorID", ctypes.c_uint16),
        ("ProductID", ctypes.c_uint16),
        ("VersionNumber", ctypes.c_uint16),
    ]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ("Usage", ctypes.c_uint16),
        ("UsagePage", ctypes.c_uint16),
        ("InputReportByteLength", ctypes.c_uint16),
        ("OutputReportByteLength", ctypes.c_uint16),
        ("FeatureReportByteLength", ctypes.c_uint16),
        ("Reserved", ctypes.c_uint16 * 17),
        ("NumberLinkCollectionNodes", ctypes.c_uint16),
        ("NumberInputButtonCaps", ctypes.c_uint16),
        ("NumberInputValueCaps", ctypes.c_uint16),
        ("NumberInputDataIndices", ctypes.c_uint16),
        ("NumberOutputButtonCaps", ctypes.c_uint16),
        ("NumberOutputValueCaps", ctypes.c_uint16),
        ("NumberOutputDataIndices", ctypes.c_uint16),
        ("NumberFeatureButtonCaps", ctypes.c_uint16),
        ("NumberFeatureValueCaps", ctypes.c_uint16),
        ("NumberFeatureDataIndices", ctypes.c_uint16),
    ]


HIDDLL.HidD_GetAttributes.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDD_ATTRIBUTES)]
HIDDLL.HidD_GetAttributes.restype = ctypes.c_bool
HIDDLL.HidD_GetPreparsedData.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
HIDDLL.HidD_GetPreparsedData.restype = ctypes.c_bool
HIDDLL.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
HIDDLL.HidD_FreePreparsedData.restype = ctypes.c_bool
HIDDLL.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
HIDDLL.HidP_GetCaps.restype = ctypes.c_long
HIDDLL.HidD_GetProductString.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_ulong]
HIDDLL.HidD_GetProductString.restype = ctypes.c_bool
HIDDLL.HidD_GetManufacturerString.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_ulong]
HIDDLL.HidD_GetManufacturerString.restype = ctypes.c_bool
HIDDLL.HidD_GetSerialNumberString.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_ulong]
HIDDLL.HidD_GetSerialNumberString.restype = ctypes.c_bool

SETUPAPI.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint32]
SETUPAPI.SetupDiGetClassDevsW.restype = ctypes.c_void_p
SETUPAPI.SetupDiEnumDeviceInterfaces.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.c_uint32, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)]
SETUPAPI.SetupDiEnumDeviceInterfaces.restype = ctypes.c_bool
SETUPAPI.SetupDiGetDeviceInterfaceDetailW.argtypes = [ctypes.c_void_p, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA), ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
SETUPAPI.SetupDiGetDeviceInterfaceDetailW.restype = ctypes.c_bool
SETUPAPI.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
SETUPAPI.SetupDiDestroyDeviceInfoList.restype = ctypes.c_bool

K32.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
K32.CreateFileW.restype = ctypes.c_void_p
K32.CloseHandle.argtypes = [ctypes.c_void_p]
K32.CloseHandle.restype = ctypes.c_bool
K32.ReadFile.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
K32.ReadFile.restype = ctypes.c_bool
K32.WriteFile.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
K32.WriteFile.restype = ctypes.c_bool
K32.DeviceIoControl.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
K32.DeviceIoControl.restype = ctypes.c_bool
K32.CreateEventW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_bool, ctypes.c_wchar_p]
K32.CreateEventW.restype = ctypes.c_void_p
K32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
K32.WaitForSingleObject.restype = ctypes.c_uint32
K32.CancelIoEx.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
K32.CancelIoEx.restype = ctypes.c_bool


class OVERLAPPED(ctypes.Structure):
    _fields_ = [
        ("Internal", ctypes.c_void_p),
        ("InternalHigh", ctypes.c_void_p),
        ("Offset", ctypes.c_uint32),
        ("OffsetHigh", ctypes.c_uint32),
        ("hEvent", ctypes.c_void_p),
    ]


class HIDP_VALUE_CAPS(ctypes.Structure):
    _fields_ = [
        ("UsagePage", ctypes.c_uint16),
        ("ReportID", ctypes.c_ubyte),
        ("IsAlias", ctypes.c_ubyte),
        ("BitField", ctypes.c_uint16),
        ("LinkCollection", ctypes.c_uint16),
        ("LinkUsage", ctypes.c_uint16),
        ("LinkUsagePage", ctypes.c_uint16),
        ("IsRange", ctypes.c_ubyte),
        ("IsStringRange", ctypes.c_ubyte),
        ("IsDesignatorRange", ctypes.c_ubyte),
        ("IsAbsolute", ctypes.c_ubyte),
        ("HasNull", ctypes.c_ubyte),
        ("Reserved", ctypes.c_ubyte),
        ("BitSize", ctypes.c_uint16),
        ("ReportCount", ctypes.c_uint16),
        ("Reserved2", ctypes.c_uint16 * 5),
        ("LogicalMin", ctypes.c_int32),
        ("LogicalMax", ctypes.c_int32),
        ("PhysicalMin", ctypes.c_int32),
        ("PhysicalMax", ctypes.c_int32),
        ("UsageMin", ctypes.c_uint16),
        ("UsageMax", ctypes.c_uint16),
    ]


HIDP_INPUT, HIDP_OUTPUT, HIDP_FEATURE = 0, 1, 2
HIDDLL.HidP_GetValueCaps.argtypes = [ctypes.c_int, ctypes.POINTER(HIDP_VALUE_CAPS),
                                     ctypes.POINTER(ctypes.c_ushort), ctypes.c_void_p]
HIDDLL.HidP_GetValueCaps.restype = ctypes.c_long


class HidInfo(object):
    __slots__ = ("path", "vid", "pid", "version", "usage_page", "usage",
                 "in_len", "out_len", "feat_len", "product", "manufacturer", "serial")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    @property
    def vidpid(self):
        return "%04X:%04X" % (self.vid or 0, self.pid or 0)

    def __repr__(self):
        return "<HidInfo %s p%04X u%04X in=%d out=%d feat=%d %r>" % (
            self.vidpid, self.usage_page or 0, self.usage or 0,
            self.in_len or 0, self.out_len or 0, self.feat_len or 0, self.product)


def _open(path, access, overlapped):
    flags = FILE_FLAG_OVERLAPPED if overlapped else 0
    h = K32.CreateFileW(path, access, FILE_SHARE_READ | FILE_SHARE_WRITE,
                        None, OPEN_EXISTING, flags, None)
    if h == INVALID_HANDLE_VALUE or not h:
        return None
    return h


def enumerate_hid():
    """Return a list of HidInfo for every HID top-level collection present."""
    guid = GUID.from_string(HID_GUID)
    info = SETUPAPI.SetupDiGetClassDevsW(ctypes.byref(guid), None, None,
                                        DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    if info == INVALID_HANDLE_VALUE or not info:
        return []
    out = []
    try:
        did = SP_DEVICE_INTERFACE_DATA()
        did.cbSize = ctypes.sizeof(did)
        idx = 0
        while SETUPAPI.SetupDiEnumDeviceInterfaces(info, None, ctypes.byref(guid), idx, ctypes.byref(did)):
            idx += 1
            required = ctypes.c_uint32(0)
            SETUPAPI.SetupDiGetDeviceInterfaceDetailW(info, ctypes.byref(did), None, 0,
                                                      ctypes.byref(required), None)
            if required.value <= 0:
                continue
            buf = ctypes.create_string_buffer(required.value)
            ctypes.c_uint32.from_buffer(buf).value = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
            if not SETUPAPI.SetupDiGetDeviceInterfaceDetailW(info, ctypes.byref(did), buf, required.value,
                                                             ctypes.byref(required), None):
                continue
            path = ctypes.wstring_at(ctypes.addressof(buf) + 4)

            h = _open(path, 0, False)
            if not h:
                continue
            try:
                attrs = HIDD_ATTRIBUTES()
                attrs.Size = ctypes.sizeof(attrs)
                HIDDLL.HidD_GetAttributes(h, ctypes.byref(attrs))
                prod = ctypes.create_unicode_buffer(256)
                HIDDLL.HidD_GetProductString(h, prod, 512)
                mfg = ctypes.create_unicode_buffer(256)
                HIDDLL.HidD_GetManufacturerString(h, mfg, 512)
                sn = ctypes.create_unicode_buffer(256)
                HIDDLL.HidD_GetSerialNumberString(h, sn, 512)

                caps = HIDP_CAPS()
                pp = ctypes.c_void_p()
                if HIDDLL.HidD_GetPreparsedData(h, ctypes.byref(pp)) and pp:
                    try:
                        HIDDLL.HidP_GetCaps(pp, ctypes.byref(caps))
                    finally:
                        HIDDLL.HidD_FreePreparsedData(pp)
                out.append(HidInfo(
                    path=path, vid=attrs.VendorID, pid=attrs.ProductID,
                    version=attrs.VersionNumber,
                    usage_page=caps.UsagePage, usage=caps.Usage,
                    in_len=caps.InputReportByteLength,
                    out_len=caps.OutputReportByteLength,
                    feat_len=caps.FeatureReportByteLength,
                    product=prod.value, manufacturer=mfg.value, serial=sn.value))
            finally:
                K32.CloseHandle(h)
    finally:
        SETUPAPI.SetupDiDestroyDeviceInfoList(info)
    return out


def find(vid=None, pid=None, usage_page=None, usage=None):
    res = []
    for d in enumerate_hid():
        if vid is not None and d.vid != vid:
            continue
        if pid is not None and d.pid != pid:
            continue
        if usage_page is not None and d.usage_page != usage_page:
            continue
        if usage is not None and d.usage != usage:
            continue
        res.append(d)
    return res


class HidDevice(object):
    """A HID interface with separate read/write handles.

    A blocking read must never share a handle with a write: that is documented
    to take the process down on some vendor dongles.  So reads use their own
    handle flagged OVERLAPPED, writes/feature I/O use plain handles.
    """

    def __init__(self, info):
        self.info = info
        self._h_read = _open(info.path, GENERIC_READ, True)
        self._h_rw = _open(info.path, GENERIC_READ | GENERIC_WRITE, False)
        if not self._h_rw:
            self._h_rw = _open(info.path, 0, False)  # system-exclusive collection
        if not (self._h_read or self._h_rw):
            raise OSError("cannot open HID interface: %s" % info.path)
        self._event = K32.CreateEventW(None, True, False, None) if self._h_read else None

    def close(self):
        for attr in ("_h_read", "_h_rw"):
            h = getattr(self, attr, None)
            if h:
                K32.CloseHandle(h)
                setattr(self, attr, None)
        if getattr(self, "_event", None):
            K32.CloseHandle(self._event)
            self._event = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    # -- Feature reports -------------------------------------------------
    def get_feature(self, report_id, length=None):
        if not self._h_rw:
            return None
        n = length or self.info.feat_len or 65
        n = max(n, 2)
        buf = ctypes.create_string_buffer(n)
        buf[0] = bytes([report_id & 0xFF])
        if not HIDDLL.HidD_GetFeature(self._h_rw, buf, n):
            return None
        return buf.raw[:n]

    def set_feature(self, data):
        if not self._h_rw:
            return False
        raw = bytes(data)
        buf = ctypes.create_string_buffer(raw, len(raw))
        return bool(HIDDLL.HidD_SetFeature(self._h_rw, buf, len(raw)))

    # -- Output / Input --------------------------------------------------
    def write_output(self, data):
        if not self._h_rw:
            return False
        raw = bytes(data)
        buf = ctypes.create_string_buffer(raw, len(raw))
        written = ctypes.c_uint32(0)
        ok = K32.WriteFile(self._h_rw, buf, len(raw), ctypes.byref(written), None)
        if not ok:
            # fall back to feature write, some dongles only accept that
            ok = bool(HIDDLL.HidD_SetFeature(self._h_rw, buf, len(raw)))
        return bool(ok)

    def read_input(self, timeout_ms=300, length=None):
        if not self._h_read:
            return None
        n = length or self.info.in_len or 65
        n = max(n, 2)
        buf = ctypes.create_string_buffer(n)
        ov = OVERLAPPED()
        ov.hEvent = K32.CreateEventW(None, True, False, None)
        try:
            read = ctypes.c_uint32(0)
            ok = K32.ReadFile(self._h_read, buf, n, ctypes.byref(read), ctypes.byref(ov))
            if not ok:
                err = ctypes.get_last_error()
                if err != 997:  # ERROR_IO_PENDING
                    return None
                rc = K32.WaitForSingleObject(ov.hEvent, timeout_ms)
                if rc != 0:  # timeout
                    K32.CancelIoEx(self._h_read, ctypes.byref(ov))
                    K32.WaitForSingleObject(ov.hEvent, 50)
                    return None
                if not K32.GetOverlappedResult(self._h_read, ctypes.byref(ov), ctypes.byref(read), False):
                    return None
            return buf.raw[:read.value]
        finally:
            if ov.hEvent:
                K32.CloseHandle(ov.hEvent)

    def drain_input(self, timeout_ms=20, rounds=16):
        out = []
        for _ in range(rounds):
            r = self.read_input(timeout_ms)
            if not r:
                break
            out.append(r)
        return out

    def value_caps(self, kind):
        """HIDP_VALUE_CAPS entries for HidP_Input / HidP_Output / HidP_Feature."""
        h = self._h_rw or self._h_read
        if not h:
            return []
        pp = ctypes.c_void_p()
        if not HIDDLL.HidD_GetPreparsedData(h, ctypes.byref(pp)) or not pp:
            return []
        try:
            caps = HIDP_CAPS()
            HIDDLL.HidP_GetCaps(pp, ctypes.byref(caps))
            n = {HIDP_INPUT: caps.NumberInputValueCaps,
                 HIDP_OUTPUT: caps.NumberOutputValueCaps,
                 HIDP_FEATURE: caps.NumberFeatureValueCaps}[kind]
            if not n:
                return []
            arr = (HIDP_VALUE_CAPS * n)()
            length = ctypes.c_ushort(n)
            rc = HIDDLL.HidP_GetValueCaps(kind, arr, ctypes.byref(length), pp)
            if rc < 0:
                return []
            return [arr[i] for i in range(length.value)]
        finally:
            HIDDLL.HidD_FreePreparsedData(pp)

    def report_descriptor(self):
        h = self._h_rw or self._h_read
        if not h:
            return b""
        buf = ctypes.create_string_buffer(4096)
        ret = ctypes.c_uint32(0)
        ok = K32.DeviceIoControl(h, IOCTL_HID_GET_REPORT_DESCRIPTOR, None, 0,
                                 buf, 4096, ctypes.byref(ret), None)
        return buf.raw[:ret.value] if ok else b""


K32.GetOverlappedResult.argtypes = [ctypes.c_void_p, ctypes.POINTER(OVERLAPPED), ctypes.POINTER(ctypes.c_uint32), ctypes.c_bool]
K32.GetOverlappedResult.restype = ctypes.c_bool
