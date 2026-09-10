<# Dispatches one reviewed Morrowind campaign into interactive Session 1. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('Primary','Repeat','BaselineControl')][string]$Phase,
    [Parameter(Mandatory)][ValidateSet('MORROWIND-FRESH','MORROWIND-SNAPSHOT')][string]$Workload,
    [Parameter(Mandatory)][ValidateSet('VULKAN','OPENGL')][string]$Renderer,
    [Parameter(Mandatory)][string]$CampaignId,
    [Parameter(Mandatory)][string]$BuildManifest,
    [Parameter(Mandatory)][string]$WorkloadManifest,
    [Parameter(Mandatory)][string]$ResultsRoot,
    [Parameter(Mandatory)][string]$RunsRoot,
    [Parameter(Mandatory)][string]$HddSafetyTool,
    [Parameter(Mandatory)][string]$SendKeyTool,
    [Parameter(Mandatory)][string]$CaptureTool
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$BuildManifest = (Resolve-Path -LiteralPath $BuildManifest).Path
$WorkloadManifest = (Resolve-Path -LiteralPath $WorkloadManifest).Path
$HddSafetyTool = (Resolve-Path -LiteralPath $HddSafetyTool).Path
$SendKeyTool = (Resolve-Path -LiteralPath $SendKeyTool).Path
$CaptureTool = (Resolve-Path -LiteralPath $CaptureTool).Path
$ResultsRoot = [IO.Path]::GetFullPath($ResultsRoot)
$RunsRoot = [IO.Path]::GetFullPath($RunsRoot)
$connection = [Management.Automation.Runspaces.NamedPipeConnectionInfo]::new(
    'GuiTestConsole', 5000)
$runspace = [runspacefactory]::CreateRunspace($connection)
$runspace.Open()
$powershell = [powershell]::Create()
$powershell.Runspace = $runspace
try {
    [void]$powershell.AddCommand((Join-Path $PSScriptRoot 'run-morrowind-campaign.ps1'))
    [void]$powershell.AddParameters(@{
        Phase = $Phase
        Workload = $Workload
        Renderer = $Renderer
        CampaignId = $CampaignId
        BuildManifest = $BuildManifest
        ResultsRoot = $ResultsRoot
        RunsRoot = $RunsRoot
        WorkloadManifest = $WorkloadManifest
        CellRunner = (Join-Path $PSScriptRoot 'run-morrowind-qualification-cell.ps1')
        HddSafetyTool = $HddSafetyTool
        SendKeyTool = $SendKeyTool
        CaptureTool = $CaptureTool
    })
    $output = $powershell.Invoke()
    foreach ($line in @($output)) { [Console]::WriteLine([string]$line) }
    if ($powershell.HadErrors) {
        throw ($powershell.Streams.Error | Out-String)
    }
} finally {
    $powershell.Dispose()
    $runspace.Dispose()
}
