[CmdletBinding()]
param(
    [string]$BuildOverrideRoot = '',
    [string]$DiagnosticRoot = '',
    [ValidateRange(15, 120)][int]$DurationSeconds = 30,
    [switch]$AllowStoppedRetailCampaign
)
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) {
    throw 'dispatch-pgr2-vk-telemetry-diagnostic.ps1 requires PowerShell 7 (pwsh).'
}
$labRoot = $env:XEMU_LAB_ROOT
if ([string]::IsNullOrWhiteSpace($labRoot)) {
    throw 'Set XEMU_LAB_ROOT before dispatching the diagnostic.'
}
$connection = [Management.Automation.Runspaces.NamedPipeConnectionInfo]::new(
    'GuiTestConsole', 5000
)
$runspace = [runspacefactory]::CreateRunspace($connection)
$runspace.Open()
$powershell = [powershell]::Create()
$powershell.Runspace = $runspace
try {
    [void]$powershell.AddScript({
        param([string]$Value)
        $env:XEMU_LAB_ROOT = $Value
    }).AddArgument($labRoot)
    [void]$powershell.AddStatement()
    [void]$powershell.AddScript({
        param([string]$Script, [string]$Override, [string]$Root, [int]$Seconds, [bool]$Stopped)
        $arguments = @{ DurationSeconds = $Seconds }
        if ($Override) { $arguments.BuildOverrideRoot = $Override }
        if ($Root) { $arguments.DiagnosticRoot = $Root }
        if ($Stopped) { $arguments.AllowStoppedRetailCampaign = $true }
        & $Script @arguments
    })
    [void]$powershell.AddArgument((Join-Path $PSScriptRoot 'run-pgr2-vk-telemetry-diagnostic.ps1'))
    [void]$powershell.AddArgument($BuildOverrideRoot)
    [void]$powershell.AddArgument($DiagnosticRoot)
    [void]$powershell.AddArgument($DurationSeconds)
    [void]$powershell.AddArgument([bool]$AllowStoppedRetailCampaign)
    $output = $powershell.Invoke()
    foreach ($line in @($output)) { [Console]::WriteLine([string]$line) }
    if ($powershell.HadErrors) {
        throw ($powershell.Streams.Error | Out-String)
    }
} finally {
    $powershell.Dispose()
    $runspace.Dispose()
}
