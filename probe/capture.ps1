param([int]$ProcId, [string]$Out = "$env:TEMP\shot.png")

Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class Win32Cap {
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int n);
}
'@

$p = Get-Process -Id $ProcId -ErrorAction Stop
$h = $p.MainWindowHandle
if ($h -eq [IntPtr]::Zero) { Write-Output "no window for pid $ProcId"; exit 1 }
[void][Win32Cap]::ShowWindow($h, 9)
[void][Win32Cap]::SetForegroundWindow($h)
Start-Sleep -Milliseconds 900
$r = New-Object Win32Cap+RECT
[void][Win32Cap]::GetWindowRect($h, [ref]$r)
$w = $r.Right - $r.Left; $hh = $r.Bottom - $r.Top
Write-Output "rect $($r.Left),$($r.Top) ${w}x${hh}"
$bmp = New-Object System.Drawing.Bitmap($w, $hh)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($r.Left, $r.Top, 0, 0, $bmp.Size)
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
Write-Output "saved $Out"
