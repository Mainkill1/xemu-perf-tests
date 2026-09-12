param(
    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 255)]
    [int]$VirtualKey,
    [int]$ProcessId = 0,
    [ValidateRange(25, 2000)]
    [int]$HoldMilliseconds = 100,
    [ValidateSet('Tap', 'Down', 'Up')]
    [string]$State = 'Tap'
)

$ErrorActionPreference = 'Stop'
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class XemuKeyNative {
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr window);
    [DllImport("user32.dll")]
    public static extern void keybd_event(byte key, byte scan, uint flags, UIntPtr extra);
}
'@

$process = if ($ProcessId -gt 0) {
    Get-Process -Id $ProcessId -ErrorAction Stop
} else {
    Get-Process xemu -ErrorAction Stop | Select-Object -First 1
}
if ($process.MainWindowHandle -eq [IntPtr]::Zero) {
    throw 'xemu has no visible window in this session.'
}
[void][XemuKeyNative]::SetForegroundWindow($process.MainWindowHandle)
Start-Sleep -Milliseconds 250
if ($State -ne 'Up') {
    [XemuKeyNative]::keybd_event([byte]$VirtualKey, 0, 0, [UIntPtr]::Zero)
}
if ($State -eq 'Tap') {
    Start-Sleep -Milliseconds $HoldMilliseconds
}
if ($State -ne 'Down') {
    [XemuKeyNative]::keybd_event([byte]$VirtualKey, 0, 2, [UIntPtr]::Zero)
}
