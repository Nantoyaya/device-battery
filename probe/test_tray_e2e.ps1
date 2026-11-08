param([int]$AppPid)

Add-Type @'
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public class W32 {
  public delegate bool Proc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(Proc p, IntPtr l);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);

  public static IntPtr FindByClass(uint target, string cls) {
    IntPtr found = IntPtr.Zero;
    EnumWindows((h, l) => {
      uint pid; GetWindowThreadProcessId(h, out pid);
      if (pid == target) {
        var c = new StringBuilder(256); GetClassName(h, c, 256);
        if (c.ToString() == cls) { found = h; return false; }
      }
      return true;
    }, IntPtr.Zero);
    return found;
  }
}
'@

$tray = [W32]::FindByClass([uint32]$AppPid, "DeviceBatteryTrayWnd")
$proc = Get-Process -Id $AppPid -ErrorAction SilentlyContinue
$panel = if ($proc) { $proc.MainWindowHandle } else { [IntPtr]::Zero }
Write-Output "tray hwnd=$tray  panel hwnd=$panel"
if ($tray -eq [IntPtr]::Zero) { Write-Output "FAIL: tray window not found"; exit 1 }

Write-Output ("panel visible (start)     : " + [W32]::IsWindowVisible($panel))

[void][W32]::PostMessage($panel, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero)
Start-Sleep -Milliseconds 800
$proc.Refresh()
$panel2 = if ($proc) { $proc.MainWindowHandle } else { [IntPtr]::Zero }
Write-Output ("panel visible (after X)   : " + [W32]::IsWindowVisible($panel2))

[void][W32]::SendMessage($tray, 0x0401, [IntPtr]::Zero, [IntPtr]0x0202)
Start-Sleep -Milliseconds 1200
$proc.Refresh()
$panel3 = if ($proc) { $proc.MainWindowHandle } else { [IntPtr]::Zero }
Write-Output ("panel visible (tray click): " + [W32]::IsWindowVisible($panel3))

[void][W32]::SendMessage($tray, 0x0111, [IntPtr]1002, [IntPtr]::Zero)
Start-Sleep -Milliseconds 400
Write-Output "refresh command sent"

powershell -NoProfile -ExecutionPolicy Bypass -File "$PSScriptRoot\capture.ps1" -ProcId $AppPid -Out "$env:TEMP\panel_after.png" 2>&1 | Out-Null

[void][W32]::SendMessage($tray, 0x0111, [IntPtr]1004, [IntPtr]::Zero)
Start-Sleep -Milliseconds 1600
$alive = Get-Process -Id $AppPid -ErrorAction SilentlyContinue
Write-Output ("process alive after exit  : " + [bool]$alive)
Write-Output ("tray after exit           : " + [W32]::FindByClass([uint32]$AppPid, "DeviceBatteryTrayWnd"))
