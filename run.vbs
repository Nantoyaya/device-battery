' run.vbs —— 无黑窗启动设备电量面板
Option Explicit

Dim fso, shell, here, py, candidate, i, paths
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

here = fso.GetParentFolderName(WScript.ScriptFullName)

' 1) 优先用和本机 python.exe 同目录的 pythonw.exe
py = ""
candidate = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe")
If fso.FileExists(candidate) Then py = candidate

' 2) 再扫一遍常见的按用户/全局安装位置
If py = "" Then
    paths = Array( _
        shell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe"), _
        shell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe"), _
        shell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python310\pythonw.exe"), _
        "C:\Program Files\Python312\pythonw.exe", _
        "C:\Program Files\Python311\pythonw.exe")
    For i = 0 To UBound(paths)
        If fso.FileExists(paths(i)) Then
            py = paths(i)
            Exit For
        End If
    Next
End If

' 3) 最后交给 PATH
If py = "" Then py = "pythonw.exe"

shell.CurrentDirectory = here
shell.Run """" & py & """ """ & here & "\app.py""", 0, False
