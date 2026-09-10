<#
.SYNOPSIS
Runs one hash-pinned MORROWIND-FRESH or MORROWIND-SNAPSHOT qualification cell.
.DESCRIPTION
The workload manifest selects launch and input admission. Both workloads use
the same display-write cadence/tail collector. The private HDD and owned xemu
process are cleaned on success and failure; source inputs are hash-checked
before and after the run.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Root,
    [Parameter(Mandatory)][ValidateSet('MORROWIND-FRESH','MORROWIND-SNAPSHOT')][string]$Workload,
    [Parameter(Mandatory)][ValidateSet('fixed_baseline','previous_main','candidate')][string]$Role,
    [Parameter(Mandatory)][string]$Xemu,
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{64}$')][string]$XemuSha256,
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$SourceCommit,
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$SourceTree,
    [Parameter(Mandatory)][ValidateSet('VULKAN','OPENGL')][string]$Renderer,
    [Parameter(Mandatory)][string]$WorkloadManifest,
    [Parameter(Mandatory)][string]$HddSafetyTool,
    [Parameter(Mandatory)][string]$SendKeyTool,
    [Parameter(Mandatory)][string]$CaptureTool,
    [ValidateSet(0,2)][int]$PresentInterval = 0,
    [string]$Control = (Join-Path $PSScriptRoot 'morrowind-control.ps1')
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ([Diagnostics.Process]::GetCurrentProcess().SessionId -ne 1) {
    throw 'Use the Session 1 GUI pipe'
}
if (Test-Path -LiteralPath $Root) { throw "Existing run root: $Root" }

function Get-Sha256([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Missing required file: $Path"
    }
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function Assert-Hash([string]$Path, [string]$Expected, [string]$Label) {
    $actual = Get-Sha256 $Path
    if ($actual -cne $Expected) {
        throw "$Label hash mismatch: expected=$Expected actual=$actual"
    }
}
function Save-Result {
    $temporary = $resultPath + '.tmp'
    $result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $temporary
    Move-Item -LiteralPath $temporary -Destination $resultPath -Force
}
function Get-Percentile([double[]]$Sorted, [double]$Percentile) {
    $index = [Math]::Max(
        0, [Math]::Min($Sorted.Count - 1,
            [Math]::Ceiling($Percentile * $Sorted.Count) - 1))
    return [double]$Sorted[$index]
}
function Resolve-InputIdentity([object]$Identity, [string]$Label) {
    if ($null -eq $Identity -or -not $Identity.path -or
        $Identity.sha256 -notmatch '^[0-9a-f]{64}$') {
        throw "Invalid runtime identity: $Label"
    }
    $path = if ([IO.Path]::IsPathRooted([string]$Identity.path)) {
        [string]$Identity.path
    } else {
        Join-Path $manifestRoot ([string]$Identity.path)
    }
    return [pscustomobject]@{
        path = [IO.Path]::GetFullPath($path)
        sha256 = [string]$Identity.sha256
    }
}

$resolvedManifest = (Resolve-Path -LiteralPath $WorkloadManifest).Path
$manifestRoot = Split-Path -Parent $resolvedManifest
$manifest = Get-Content -LiteralPath $resolvedManifest -Raw | ConvertFrom-Json
if ($manifest.schema_version -ne 1) { throw 'Workload manifest schema mismatch' }
if ($null -eq $manifest.PSObject.Properties['example_only']) {
    throw 'Workload manifest must declare example_only'
}
if ($manifest.example_only -eq $true) {
    throw 'Example workload manifest cannot launch a retail workload; provide a local runtime manifest'
}
$profile = $manifest.workloads.$Workload
if ($null -eq $profile) { throw "Missing workload profile: $Workload" }
$expectedMode = if ($Workload -eq 'MORROWIND-FRESH') { 'FreshBoot' } else { 'Snapshot' }
if ($profile.launch_mode -cne $expectedMode) { throw 'Workload launch mode mismatch' }
if ($Workload -eq 'MORROWIND-FRESH' -and $null -ne $profile.snapshot) {
    throw 'MORROWIND-FRESH must not restore a snapshot'
}
if ($Workload -eq 'MORROWIND-SNAPSHOT' -and -not $profile.snapshot) {
    throw 'MORROWIND-SNAPSHOT requires a snapshot'
}
$config = Resolve-InputIdentity $profile.inputs.configs.$Renderer "config.$Renderer"
$seed = Resolve-InputIdentity $profile.inputs.seed 'seed'
$disc = Resolve-InputIdentity $profile.inputs.disc 'disc'
$eeprom = Resolve-InputIdentity $profile.inputs.eeprom 'eeprom'
Assert-Hash $Xemu $XemuSha256 'xemu executable'
Assert-Hash $seed.path $seed.sha256 'immutable Morrowind seed'
Assert-Hash $config.path $config.sha256 'immutable Morrowind config'
Assert-Hash $disc.path $disc.sha256 'Morrowind disc'
Assert-Hash $eeprom.path $eeprom.sha256 'immutable EEPROM'

$resultPath = Join-Path $Root 'result.json'
$private = Join-Path $Root 'private-hdd.qcow2'
$result = [ordered]@{
    schema_version = 3
    status = 'running'
    workload = $Workload
    launch_mode = $profile.launch_mode
    role = $Role
    source_commit = $SourceCommit
    source_tree = $SourceTree
    executable_sha256 = $XemuSha256
    renderer = $Renderer
    present_interval = if ($PresentInterval -eq 2) { 2 } else { 1 }
    present_interval_explicit = ($PresentInterval -eq 2)
    snapshot = $profile.snapshot
    input_sequence = @($profile.input_steps)
    post_input_delay_seconds = $profile.post_input_delay_seconds
    duration_seconds = $profile.measurement.duration_seconds
    metric = 'NV2A display-write increment cadence proxy; not rendered/displayed FPS'
    private_hdd_deleted = $false
    cleanup = ''
}
$result.runner_sha256 = Get-Sha256 $PSCommandPath
$result.control_sha256 = Get-Sha256 $Control
$result.workload_manifest_sha256 = Get-Sha256 $resolvedManifest
$controlTools = @{
    HddSafetyTool = $HddSafetyTool
    SendKeyTool = $SendKeyTool
    CaptureTool = $CaptureTool
    Eeprom = $eeprom.path
    EepromSha256 = $eeprom.sha256
}
$launched = $false
$closed = $false
$captureLabels = @()
try {
    & $Control -Action Init -Root $Root -SourceHdd $seed.path `
        -SourceSha256 $seed.sha256 @controlTools | Out-Null
    $snapshot = if ($null -eq $profile.snapshot) { '' } else { [string]$profile.snapshot }
    & $Control -Action Launch -Root $Root -Xemu $Xemu -XemuSha256 $XemuSha256 `
        -Renderer $Renderer -PresentInterval $PresentInterval `
        -BaseConfig $config.path -BaseConfigSha256 $config.sha256 `
        -Disc $disc.path -DiscSha256 $disc.sha256 -Snapshot $snapshot `
        @controlTools | Out-Null
    $launched = $true
    $deadline = [DateTime]::UtcNow.AddSeconds(90)
    do {
        try {
            $statusText = @(& $Control -Action Status -Root $Root `
                @controlTools 2>$null)[0]
            $status = $statusText | ConvertFrom-Json
            $ready = $status.running -eq $true -and $status.status -eq 'running'
        } catch {
            $ready = $false
        }
        if (-not $ready) { Start-Sleep -Milliseconds 250 }
    } while (-not $ready -and [DateTime]::UtcNow -lt $deadline)
    if (-not $ready) { throw "$Workload did not reach QMP running state within 90 seconds" }
    $result.qmp_ready_utc = [DateTime]::UtcNow.ToString('o')

    foreach ($step in @($profile.input_steps)) {
        if ($step.delay_seconds -gt 0) { Start-Sleep -Seconds $step.delay_seconds }
        $label = [string]$step.capture_label
        & $Control -Action Capture -Root $Root -Label $label `
            @controlTools | Out-Null
        $captureLabels += $label
        & $Control -Action Key -Root $Root -VirtualKey ([int]$step.virtual_key) `
            -HoldMilliseconds 150 @controlTools | Out-Null
    }
    if ($profile.post_input_delay_seconds -gt 0) {
        Start-Sleep -Seconds $profile.post_input_delay_seconds
    }
    & $Control -Action Capture -Root $Root -Label 'measurement-start' `
        @controlTools | Out-Null
    $captureLabels += 'measurement-start'
    $windowStart = [DateTime]::UtcNow
    $result.measurement_started_utc = $windowStart.ToString('o')
    Start-Sleep -Seconds ([int]$profile.measurement.duration_seconds)
    $windowEnd = [DateTime]::UtcNow
    $result.measurement_ended_utc = $windowEnd.ToString('o')
    $result.measurement_elapsed_seconds = ($windowEnd - $windowStart).TotalSeconds
    & $Control -Action Capture -Root $Root -Label 'measurement-end' `
        @controlTools | Out-Null
    $captureLabels += 'measurement-end'

    & $Control -Action Close -Root $Root @controlTools | Out-Null
    $closed = $true
    $state = Get-Content -LiteralPath (Join-Path $Root 'control.json') -Raw |
        ConvertFrom-Json
    if ($state.status -ne 'closed') {
        throw "Unexpected close status: $($state.status)"
    }
    $trace = Join-Path $state.launch_dir 'guest-flips.log'
    $timestamps = @()
    $previousNew = $null
    foreach ($line in Get-Content -LiteralPath $trace) {
        if ($line -notmatch '^(\S+) nv2a_pgraph_flip_increment_write 0x([0-9a-fA-F]+) -> 0x([0-9a-fA-F]+)$') {
            continue
        }
        $time = [DateTimeOffset]::Parse($Matches[1]).UtcDateTime
        $old = [Convert]::ToUInt32($Matches[2], 16)
        $new = [Convert]::ToUInt32($Matches[3], 16)
        if ($null -ne $previousNew -and $old -ne $previousNew) {
            throw 'Display-write trace continuity failed'
        }
        $previousNew = $new
        if ($time -ge $windowStart -and $time -le $windowEnd) {
            $timestamps += $time
        }
    }
    if ($timestamps.Count -lt 2) {
        throw 'Fewer than two display-write events in measurement window'
    }
    for ($index = 1; $index -lt $timestamps.Count; $index++) {
        if ($timestamps[$index] -le $timestamps[$index - 1]) {
            throw 'Display-write timestamps were not strictly increasing'
        }
    }
    $intervals = @()
    for ($index = 1; $index -lt $timestamps.Count; $index++) {
        $intervals += ($timestamps[$index] - $timestamps[$index - 1]).TotalMilliseconds
    }
    [double[]]$sorted = @($intervals | Sort-Object)
    $span = ($timestamps[-1] - $timestamps[0]).TotalSeconds
    $result.display_write_events = $timestamps.Count
    $result.display_write_intervals = $timestamps.Count - 1
    $result.display_write_events_per_window_second =
        $timestamps.Count / $result.measurement_elapsed_seconds
    $result.display_write_interval_cadence_per_second =
        ($timestamps.Count - 1) / $span
    $result.average_fps_proxy = $result.display_write_interval_cadence_per_second
    $result.frame_interval_average_ms = ($intervals | Measure-Object -Average).Average
    $result.frame_interval_p95_ms = Get-Percentile $sorted 0.95
    $result.frame_interval_p99_ms = Get-Percentile $sorted 0.99
    $result.frame_interval_max_ms = ($intervals | Measure-Object -Maximum).Maximum
    $result.frame_interval_worst_ms = @(
        $intervals | Sort-Object -Descending |
            Select-Object -First ([int]$profile.measurement.worst_interval_count))
    $result.frame_stall_threshold_ms = [int]$profile.measurement.stall_threshold_ms
    $result.frame_stall_count = @(
        $intervals | Where-Object {
            $_ -ge [int]$profile.measurement.stall_threshold_ms
        }).Count
    $result.first_event_utc = $timestamps[0].ToString('o')
    $result.last_event_utc = $timestamps[-1].ToString('o')

    foreach ($label in $captureLabels) {
        $metadata = Get-Content -LiteralPath (
            Join-Path $state.launch_dir ($label + '.capture.json')) -Raw |
            ConvertFrom-Json
        if ($metadata.Status -ne 'ACCEPTED') {
            throw "Automated gameplay image admission failed at $label"
        }
    }
    $beforeHash = Get-Sha256 (
        Join-Path $state.launch_dir ($captureLabels[0] + '.png'))
    $measurementStartHash = Get-Sha256 (
        Join-Path $state.launch_dir 'measurement-start.png')
    if ($beforeHash -eq $measurementStartHash) {
        throw "$Workload input route produced no image transition"
    }
    $endCapture = Get-Content -LiteralPath (
        Join-Path $state.launch_dir 'measurement-end.capture.json') -Raw |
        ConvertFrom-Json
    $result.gameplay_admission =
        "PASSED: $($profile.admission.route), image transitioned, display writes advanced"
    $result.admission_route = $profile.admission.route
    $result.pre_input_image_sha256 = $beforeHash
    $result.measurement_start_image_sha256 = $measurementStartHash
    $result.final_image_validation = 'PASSED'
    $result.final_image_sha256 = Get-Sha256 (
        Join-Path $state.launch_dir 'measurement-end.png')
    $result.final_image_nonblack_ratio = $endCapture.NonBlackRatio
    $result.final_image_unique_sampled_colors = $endCapture.UniqueSampledColors

    Assert-Hash $seed.path $seed.sha256 'source HDD after measurement'
    Assert-Hash $config.path $config.sha256 'base config after measurement'
    Assert-Hash $disc.path $disc.sha256 'disc after measurement'
    $exclusive = [IO.File]::Open(
        $private, [IO.FileMode]::Open, [IO.FileAccess]::Read,
        [IO.FileShare]::None)
    $exclusive.Dispose()
    Remove-Item -LiteralPath $private
    if (Test-Path -LiteralPath $private) { throw 'Private HDD deletion failed' }
    $result.private_hdd_deleted = $true
    $result.seed_sha256_after = Get-Sha256 $seed.path
    $result.base_config_sha256_after = Get-Sha256 $config.path
    $result.status = 'complete'
} catch {
    $result.status = 'failed'
    $result.error = $_.Exception.Message
} finally {
    if ($launched -and -not $closed) {
        try {
            & $Control -Action Close -Root $Root @controlTools | Out-Null
            $closed = $true
            $result.cleanup = 'owned process closed after failure'
        } catch {
            $result.cleanup = "uncertain process cleanup: $($_.Exception.Message)"
        }
    }
    if (Test-Path -LiteralPath $private) {
        try {
            $exclusive = [IO.File]::Open(
                $private, [IO.FileMode]::Open, [IO.FileAccess]::Read,
                [IO.FileShare]::None)
            $exclusive.Dispose()
            Remove-Item -LiteralPath $private
            if (Test-Path -LiteralPath $private) { throw 'Private HDD deletion failed' }
            $result.private_hdd_deleted = $true
            $result.cleanup = if ($result.cleanup) {
                $result.cleanup + '; private HDD deleted'
            } else {
                'private HDD deleted after failure'
            }
        } catch {
            $result.private_hdd_deleted = $false
            $result.cleanup = if ($result.cleanup) {
                $result.cleanup + "; uncertain private HDD cleanup: $($_.Exception.Message)"
            } else {
                "uncertain private HDD cleanup: $($_.Exception.Message)"
            }
        }
    }
    if (-not (Test-Path -LiteralPath $private)) {
        $result.private_hdd_deleted = $true
    }
    if (Test-Path -LiteralPath $Root) { Save-Result }
}
$result | ConvertTo-Json -Depth 12
if ($result.status -ne 'complete') {
    throw "Morrowind cell failed; see $resultPath"
}
