param([string]$Filter = '')

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Text;
using Microsoft.Win32.SafeHandles;

public static class HidNative
{
    [StructLayout(LayoutKind.Sequential)]
    public struct SP_DEVICE_INTERFACE_DATA
    {
        public int cbSize;
        public Guid InterfaceClassGuid;
        public int Flags;
        public IntPtr Reserved;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct HIDD_ATTRIBUTES
    {
        public int Size;
        public ushort VendorID;
        public ushort ProductID;
        public ushort VersionNumber;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct HIDP_CAPS
    {
        public ushort Usage;
        public ushort UsagePage;
        public ushort InputReportByteLength;
        public ushort OutputReportByteLength;
        public ushort FeatureReportByteLength;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 17)]
        public ushort[] Reserved;
        public ushort NumberLinkCollectionNodes;
        public ushort NumberInputButtonCaps;
        public ushort NumberInputValueCaps;
        public ushort NumberInputDataIndices;
        public ushort NumberOutputButtonCaps;
        public ushort NumberOutputValueCaps;
        public ushort NumberOutputDataIndices;
        public ushort NumberFeatureButtonCaps;
        public ushort NumberFeatureValueCaps;
        public ushort NumberFeatureDataIndices;
    }

    [DllImport("hid.dll", SetLastError = true)]
    public static extern bool HidD_GetAttributes(SafeFileHandle h, ref HIDD_ATTRIBUTES a);

    [DllImport("hid.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    public static extern bool HidD_GetProductString(SafeFileHandle h, StringBuilder buf, int len);

    [DllImport("hid.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    public static extern bool HidD_GetManufacturerString(SafeFileHandle h, StringBuilder buf, int len);

    [DllImport("hid.dll", SetLastError = true)]
    public static extern bool HidD_GetSerialNumberString(SafeFileHandle h, StringBuilder buf, int len);

    [DllImport("hid.dll", SetLastError = true)]
    public static extern bool HidD_GetPreparsedData(SafeFileHandle h, ref IntPtr preparsed);

    [DllImport("hid.dll", SetLastError = true)]
    public static extern bool HidD_FreePreparsedData(IntPtr preparsed);

    [DllImport("hid.dll", SetLastError = true)]
    public static extern int HidP_GetCaps(IntPtr preparsed, ref HIDP_CAPS caps);

    [DllImport("setupapi.dll", SetLastError = true)]
    public static extern IntPtr SetupDiGetClassDevs(ref Guid ClassGuid, IntPtr Enumerator, IntPtr hwndParent, int Flags);

    [DllImport("setupapi.dll", SetLastError = true)]
    public static extern bool SetupDiEnumDeviceInterfaces(IntPtr hDevInfo, IntPtr devInfo, ref Guid interfaceClassGuid, int memberIndex, ref SP_DEVICE_INTERFACE_DATA deviceInterfaceData);

    [DllImport("setupapi.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    public static extern bool SetupDiGetDeviceInterfaceDetail(IntPtr hDevInfo, ref SP_DEVICE_INTERFACE_DATA deviceInterfaceData, IntPtr deviceInterfaceDetailData, int deviceInterfaceDetailDataSize, ref int requiredSize, IntPtr deviceInfoData);

    [DllImport("setupapi.dll", SetLastError = true)]
    public static extern bool SetupDiDestroyDeviceInfoList(IntPtr hDevInfo);

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    public static extern SafeFileHandle CreateFile(string fileName, uint access, uint share, IntPtr sec, uint disposition, uint flags, IntPtr template);
}
'@

$HID_GUID = [Guid]'4d1e55b2-f16f-11cf-88cb-001111000030'
$DIGCF_PRESENT = 0x2
$DIGCF_DEVICEINTERFACE = 0x10
$INVALID = [IntPtr]::Zero

$hDevInfo = [HidNative]::SetupDiGetClassDevs([ref]$HID_GUID, $INVALID, $INVALID, ($DIGCF_PRESENT -bor $DIGCF_DEVICEINTERFACE))
if ($hDevInfo -eq [IntPtr]-1) { throw "SetupDiGetClassDevs failed" }

$did = New-Object HidNative+SP_DEVICE_INTERFACE_DATA
$did.cbSize = [Runtime.InteropServices.Marshal]::SizeOf($did)

$results = @()
$i = 0
while ([HidNative]::SetupDiEnumDeviceInterfaces($hDevInfo, $INVALID, [ref]$HID_GUID, $i, [ref]$did)) {
    $i++
    $req = 0
    [void][HidNative]::SetupDiGetDeviceInterfaceDetail($hDevInfo, [ref]$did, $INVALID, 0, [ref]$req, $INVALID)
    if ($req -le 0) { continue }
    $buf = [Runtime.InteropServices.Marshal]::AllocHGlobal($req)
    try {
        # cbSize of SP_DEVICE_INTERFACE_DETAIL_DATA_W: 8 on x64, 6 on x86
        [Runtime.InteropServices.Marshal]::WriteInt32($buf, $(if ([IntPtr]::Size -eq 8) { 8 } else { 6 }))
        if (-not [HidNative]::SetupDiGetDeviceInterfaceDetail($hDevInfo, [ref]$did, $buf, $req, [ref]$req, $INVALID)) { continue }
        $path = [Runtime.InteropServices.Marshal]::PtrToStringUni([IntPtr]::Add($buf, 4))
    } finally { [Runtime.InteropServices.Marshal]::FreeHGlobal($buf) }

    $h = [HidNative]::CreateFile($path, 0, 3, $INVALID, 3, 0, $INVALID)
    if ($h.IsInvalid) { continue }
    try {
        $attr = New-Object HidNative+HIDD_ATTRIBUTES
        $attr.Size = [Runtime.InteropServices.Marshal]::SizeOf($attr)
        [void][HidNative]::HidD_GetAttributes($h, [ref]$attr)

        $sb = New-Object System.Text.StringBuilder 256
        [void][HidNative]::HidD_GetProductString($h, $sb, 512)
        $product = $sb.ToString()
        $sb2 = New-Object System.Text.StringBuilder 256
        [void][HidNative]::HidD_GetManufacturerString($h, $sb2, 512)
        $mfg = $sb2.ToString()
        $sb3 = New-Object System.Text.StringBuilder 256
        [void][HidNative]::HidD_GetSerialNumberString($h, $sb3, 512)
        $serial = $sb3.ToString()

        $pp = [IntPtr]::Zero
        $caps = New-Object HidNative+HIDP_CAPS
        $capsOk = $false
        if ([HidNative]::HidD_GetPreparsedData($h, [ref]$pp) -and $pp -ne [IntPtr]::Zero) {
            try { $capsOk = ([HidNative]::HidP_GetCaps($pp, [ref]$caps) -eq 0x00110000) } finally { [void][HidNative]::HidD_FreePreparsedData($pp) }
        }

        $results += [pscustomobject]@{
            VidPid   = ('{0:X4}:{1:X4}' -f $attr.VendorID, $attr.ProductID)
            Version  = ('{0:X4}' -f $attr.VersionNumber)
            Page     = $(if ($capsOk) { '{0:X4}' -f $caps.UsagePage } else { '?' })
            Usage    = $(if ($capsOk) { '{0:X4}' -f $caps.Usage } else { '?' })
            InLen    = $(if ($capsOk) { $caps.InputReportByteLength } else { 0 })
            OutLen   = $(if ($capsOk) { $caps.OutputReportByteLength } else { 0 })
            FeatLen  = $(if ($capsOk) { $caps.FeatureReportByteLength } else { 0 })
            Product  = $product
            Mfg      = $mfg
            Serial   = $serial
            Path     = $path
        }
    } finally { $h.Dispose() }
}
[void][HidNative]::SetupDiDestroyDeviceInfoList($hDevInfo)

$results | Sort-Object VidPid, Page, Usage | ForEach-Object {
    if ($Filter -and ($_.VidPid -notmatch $Filter)) { return }
    '{0}  v{1}  page={2} usage={3}  in/out/feat={4}/{5}/{6}  prod="{7}" mfg="{8}" sn="{9}"' -f $_.VidPid, $_.Version, $_.Page, $_.Usage, $_.InLen, $_.OutLen, $_.FeatLen, $_.Product, $_.Mfg, $_.Serial
    '     ' + $_.Path
}
