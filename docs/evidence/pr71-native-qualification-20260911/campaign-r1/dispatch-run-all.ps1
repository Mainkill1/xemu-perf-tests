$ErrorActionPreference = 'Stop'
$connection = [Management.Automation.Runspaces.NamedPipeConnectionInfo]::new(
    'GuiTestConsole', 5000
)
$runspace = [runspacefactory]::CreateRunspace($connection)
$runspace.Open()
$powershell = [powershell]::Create()
$powershell.Runspace = $runspace
try {
    [void]$powershell.AddCommand((Join-Path $PSScriptRoot 'run-all-session1.ps1'))
    $output = $powershell.Invoke()
    foreach ($line in @($output)) { [Console]::WriteLine([string]$line) }
    if ($powershell.HadErrors) {
        throw ($powershell.Streams.Error | Out-String)
    }
} finally {
    $powershell.Dispose()
    $runspace.Dispose()
}
