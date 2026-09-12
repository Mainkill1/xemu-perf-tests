[CmdletBinding()]
param([string]$DiagnosticRoot = '')
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) {
    throw 'Interactive diagnostic dispatch requires PowerShell 7 (pwsh).'
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
        param([string]$value)
        $env:XEMU_LAB_ROOT = $value
    }).AddArgument($labRoot)
    [void]$powershell.AddStatement()
    [void]$powershell.AddCommand((Join-Path $PSScriptRoot 'run-pgr2-vk-telemetry-diagnostic.ps1'))
    if ($DiagnosticRoot) {
        [void]$powershell.AddParameter('DiagnosticRoot', $DiagnosticRoot)
    }
    $output = $powershell.Invoke()
    foreach ($line in @($output)) { [Console]::WriteLine([string]$line) }
    if ($powershell.HadErrors) {
        throw ($powershell.Streams.Error | Out-String)
    }
} finally {
    $powershell.Dispose()
    $runspace.Dispose()
}
