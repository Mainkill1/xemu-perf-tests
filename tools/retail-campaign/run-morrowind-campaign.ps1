<#
.SYNOPSIS
Runs one interleaved Morrowind qualification campaign in Session 1.
.DESCRIPTION
MORROWIND-FRESH and MORROWIND-SNAPSHOT are independent campaign identities.
The build manifest points at already-built candidate, previous-main, and fixed
baseline executables. This runner never builds a baseline and never starts WPR.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('Primary','Repeat','BaselineControl')][string]$Phase,
    [Parameter(Mandatory)][ValidateSet('MORROWIND-FRESH','MORROWIND-SNAPSHOT')][string]$Workload,
    [Parameter(Mandatory)][ValidateSet('VULKAN','OPENGL')][string]$Renderer,
    [Parameter(Mandatory)][ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')][string]$CampaignId,
    [Parameter(Mandatory)][string]$BuildManifest,
    [Parameter(Mandatory)][string]$WorkloadManifest,
    [Parameter(Mandatory)][string]$ResultsRoot,
    [Parameter(Mandatory)][string]$RunsRoot,
    [Parameter(Mandatory)][string]$HddSafetyTool,
    [Parameter(Mandatory)][string]$SendKeyTool,
    [Parameter(Mandatory)][string]$CaptureTool,
    [string]$CellRunner = (Join-Path $PSScriptRoot 'run-morrowind-qualification-cell.ps1')
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ([Diagnostics.Process]::GetCurrentProcess().SessionId -ne 1) {
    throw 'Campaign must run through the Session 1 GUI pipe'
}
function Assert-Clean([string]$When) {
    $active = @(Get-Process -Name xemu,PresentMon,wpr -ErrorAction SilentlyContinue)
    if ($active.Count -ne 0) {
        throw "$When rejected active xemu, PresentMon, or wpr process: $($active.Id -join ',')"
    }
}
function Save-Json([string]$Path, [object]$Value) {
    $temporary = $Path + '.tmp'
    $Value | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $temporary -Encoding utf8
    Move-Item -LiteralPath $temporary -Destination $Path -Force
}

$resolvedBuildManifest = (Resolve-Path -LiteralPath $BuildManifest).Path
$buildManifestRoot = Split-Path -Parent $resolvedBuildManifest
$builds = Get-Content -LiteralPath $resolvedBuildManifest -Raw | ConvertFrom-Json
if ($builds.schema_version -ne 1) { throw 'Build manifest schema mismatch' }
foreach ($roleName in @('fixed_baseline','previous_main','candidate')) {
    $role = $builds.builds.$roleName
    if ($null -eq $role -or $role.executable_sha256 -notmatch '^[0-9a-f]{64}$' -or
        $role.source_commit -notmatch '^[0-9a-f]{40}$' -or
        $role.source_tree -notmatch '^[0-9a-f]{40}$') {
        throw "Invalid or missing build identity: $roleName"
    }
    $role.host_executable = [IO.Path]::GetFullPath(
        $(if ([IO.Path]::IsPathRooted([string]$role.host_executable)) {
            [string]$role.host_executable
        } else {
            Join-Path $buildManifestRoot ([string]$role.host_executable)
        }))
    $actual = (Get-FileHash -LiteralPath $role.host_executable -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -cne $role.executable_sha256) {
        throw "$roleName executable hash mismatch"
    }
}
$orders = @{
    Primary = @('previous_main','candidate','candidate','previous_main')
    Repeat = @('candidate','previous_main','previous_main','candidate')
    BaselineControl = @(
        'fixed_baseline','previous_main','candidate','candidate',
        'previous_main','fixed_baseline')
}
$order = @($orders[$Phase])
$campaignRoot = Join-Path $ResultsRoot $CampaignId
if (Test-Path -LiteralPath $campaignRoot) {
    throw "Campaign output already exists: $campaignRoot"
}
New-Item -ItemType Directory -Path $campaignRoot | Out-Null
$receiptPath = Join-Path $campaignRoot 'campaign-receipt.json'
$receipt = [ordered]@{
    schema_version = 1
    status = 'running'
    campaign_id = $CampaignId
    phase = $Phase
    workload = $Workload
    renderer = $Renderer
    order = $order
    baseline_policy = 'Reuse hash-pinned fixed baseline executable and retained statistics; do not rebuild baseline'
    trace_policy = 'No WPR/ETL in qualification campaign'
    started_utc = [DateTime]::UtcNow.ToString('O')
    runs = @()
}
Save-Json $receiptPath $receipt
try {
    for ($index = 0; $index -lt $order.Count; $index++) {
        $roleName = $order[$index]
        $role = $builds.builds.$roleName
        $runId = '{0}-{1:D2}-{2}-{3}-{4}' -f $CampaignId, ($index + 1),
            $roleName, $Workload.ToLowerInvariant(), $Renderer.ToLowerInvariant()
        Assert-Clean "preflight $runId"
        $root = Join-Path $RunsRoot $runId
        $json = & $CellRunner -Root $root -Workload $Workload -Role $roleName `
            -Xemu $role.host_executable -XemuSha256 $role.executable_sha256 `
            -SourceCommit $role.source_commit -SourceTree $role.source_tree `
            -Renderer $Renderer -PresentInterval 0 `
            -WorkloadManifest $WorkloadManifest -HddSafetyTool $HddSafetyTool `
            -SendKeyTool $SendKeyTool -CaptureTool $CaptureTool
        $result = ($json | Out-String) | ConvertFrom-Json
        if ($result.status -ne 'complete' -or
            $result.gameplay_admission -notlike 'PASSED:*' -or
            $result.private_hdd_deleted -ne $true) {
            throw "$Workload admission or cleanup failed for $runId"
        }
        Assert-Clean "postflight $runId"
        $receipt.runs += @([ordered]@{
            ordinal = $index + 1
            role = $roleName
            run_id = $runId
            source_commit = $role.source_commit
            source_tree = $role.source_tree
            executable_sha256 = $role.executable_sha256
            status = $result.status
            cadence_per_second = $result.display_write_interval_cadence_per_second
            average_interval_ms = $result.frame_interval_average_ms
            p95_ms = $result.frame_interval_p95_ms
            p99_ms = $result.frame_interval_p99_ms
            max_ms = $result.frame_interval_max_ms
            stall_count = $result.frame_stall_count
            worst_intervals_ms = $result.frame_interval_worst_ms
            evidence = $root
        })
        Save-Json $receiptPath $receipt
    }
    Assert-Clean 'campaign completion'
    $receipt.status = 'complete'
    $receipt.completed_utc = [DateTime]::UtcNow.ToString('O')
    Save-Json $receiptPath $receipt
} catch {
    $originalError = $_
    $receipt.status = 'failed'
    $receipt.error = $originalError.Exception.Message
    $receipt.failed_utc = [DateTime]::UtcNow.ToString('O')
    try {
        Assert-Clean 'failure-path cleanup audit'
        $receipt.cleanup_audit = 'clean'
    } catch {
        $receipt.cleanup_audit = 'failed'
        $receipt.cleanup_error = $_.Exception.Message
    }
    Save-Json $receiptPath $receipt
    throw $originalError
}
$receipt
