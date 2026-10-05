[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('baseline', 'candidate')][string]$Role,
    [Parameter(Mandatory)][string]$Xemu,
    [Parameter(Mandatory)][string]$ExpectedXemuSha256,
    [Parameter(Mandatory)][string]$SourceCommit,
    [Parameter(Mandatory)][string]$SourceTree,
    [Parameter(Mandatory)][ValidateSet('VULKAN', 'OPENGL')][string]$Renderer,
    [Parameter(Mandatory)][string]$Disc,
    [Parameter(Mandatory)][string]$ExpectedDiscSha256,
    [Parameter(Mandatory)][string]$SeedHdd,
    [Parameter(Mandatory)][string]$ExpectedSeedSha256,
    [Parameter(Mandatory)][string]$BaseConfig,
    [Parameter(Mandatory)][string]$ExpectedBaseConfigSha256,
    [Parameter(Mandatory)][string]$CaptureRunner,
    [Parameter(Mandatory)][string]$ExpectedCaptureRunnerSha256,
    [Parameter(Mandatory)][string]$Launcher,
    [Parameter(Mandatory)][string]$ExpectedLauncherSha256,
    [Parameter(Mandatory)][string]$CaptureRoot,
    [Parameter(Mandatory)][string]$RunId,
    [ValidateRange(10, 300)][int]$DurationSeconds = 60,
    [ValidateRange(0, 300)][int]$WarmupSeconds = 30
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Get-Sha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Assert-Identity([string]$Path, [string]$ExpectedSha256, [string]$Label) {
    if ($ExpectedSha256 -notmatch '^[0-9a-fA-F]{64}$') {
        throw "$Label expected SHA-256 is invalid."
    }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label does not exist: $Path"
    }
    $actual = Get-Sha256 $Path
    if ($actual -cne $ExpectedSha256.ToLowerInvariant()) {
        throw "$Label SHA-256 mismatch: expected=$ExpectedSha256 actual=$actual"
    }
    return [ordered]@{
        path = [System.IO.Path]::GetFullPath((Resolve-Path -LiteralPath $Path).Path)
        sha256 = $actual
    }
}

function Write-JsonAtomic([string]$Path, [object]$Value) {
    $directory = [System.IO.Path]::GetDirectoryName(
        [System.IO.Path]::GetFullPath($Path))
    if (-not (Test-Path -LiteralPath $directory -PathType Container)) {
        throw "Receipt directory does not exist: $directory"
    }
    $temporary = Join-Path $directory (
        '.' + [System.IO.Path]::GetFileName($Path) + '.' +
        [guid]::NewGuid().ToString('N') + '.tmp')
    $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes(
        (($Value | ConvertTo-Json -Depth 8) + "`n"))
    $stream = $null
    try {
        $stream = [System.IO.FileStream]::new(
            $temporary, [System.IO.FileMode]::CreateNew,
            [System.IO.FileAccess]::Write, [System.IO.FileShare]::None,
            4096, [System.IO.FileOptions]::WriteThrough)
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
        $stream.Dispose()
        $stream = $null
        [System.IO.File]::Move($temporary, $Path)
    } finally {
        if ($null -ne $stream) { $stream.Dispose() }
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Force
        }
    }
}

if ($SourceCommit -notmatch '^[0-9a-fA-F]{40}$' -or
    $SourceTree -notmatch '^[0-9a-fA-F]{40}$') {
    throw 'Source commit and tree must be full 40-character Git object IDs.'
}
if ($RunId -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$') {
    throw 'RunId contains unsupported characters.'
}

$identity = [ordered]@{
    xemu = (Assert-Identity $Xemu $ExpectedXemuSha256 'xemu')
    disc = (Assert-Identity $Disc $ExpectedDiscSha256 'disc')
    seed_hdd = (Assert-Identity $SeedHdd $ExpectedSeedSha256 'seed HDD')
    base_config = (Assert-Identity $BaseConfig `
            $ExpectedBaseConfigSha256 'base config')
    capture_runner = (Assert-Identity $CaptureRunner `
            $ExpectedCaptureRunnerSha256 'capture runner')
    launcher = (Assert-Identity $Launcher $ExpectedLauncherSha256 'launcher')
}

$expectedLauncher = Join-Path (
    [System.IO.Path]::GetDirectoryName($identity.capture_runner.path)) `
    'start-retail-snapshot.ps1'
if (-not [string]::Equals(
        $identity.launcher.path,
        [System.IO.Path]::GetFullPath($expectedLauncher),
        [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Launcher must be the capture runner sibling used by the existing capture path.'
}

$resolvedRoot = [System.IO.Path]::GetFullPath($CaptureRoot)
$expectedEvidence = [System.IO.Path]::GetFullPath(
    (Join-Path $resolvedRoot $RunId))
if (Test-Path -LiteralPath $expectedEvidence) {
    throw "Run evidence directory already exists: $expectedEvidence"
}

$output = @(& $identity.capture_runner.path `
        -Xemu $identity.xemu.path `
        -SeedHdd $identity.seed_hdd.path `
        -BaseConfig $identity.base_config.path `
        -LaunchMode FreshBoot `
        -Snapshot '' `
        -Game PGR2 `
        -Disc $identity.disc.path `
        -CaptureRoot $resolvedRoot `
        -BuildResultName ($RunId + '.result.json') `
        -Mode PGR2-FRESH-START `
        -Renderer $Renderer `
        -SurfaceScale 1 `
        -DurationSeconds $DurationSeconds `
        -WarmupSeconds $WarmupSeconds `
        -TraceProfile CpuScheduler `
        -TraceStartMode SteadyState `
        -VkTelemetry Disabled `
        -PresentMonMode Enabled `
        -RunId $RunId)
$results = @($output | Where-Object {
        $null -ne $_ -and $null -ne $_.PSObject.Properties['status']
    })
if ($results.Count -ne 1) {
    throw "Capture runner returned $($results.Count) result objects; expected 1."
}
$result = $results[0]
if ($result.status -cne 'complete' -or
    $result.functional_status -cne 'complete' -or
    $result.measurement_status -cne 'complete') {
    throw "PGR2 FreshBoot capture did not complete: status=$($result.status)"
}
if ($result.launch_mode -cne 'FreshBoot' -or
    $result.renderer -cne $Renderer -or
    $result.xemu_sha256 -cne $identity.xemu.sha256) {
    throw 'PGR2 FreshBoot capture returned the wrong launch, renderer, or executable identity.'
}
$actualEvidence = [System.IO.Path]::GetFullPath([string]$result.evidence)
if (-not [string]::Equals(
        $actualEvidence, $expectedEvidence,
        [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Capture evidence path mismatch: $actualEvidence"
}
if ($result.focus_loss_samples -ne 0 -or
    $result.etw_lost_events -ne 0 -or
    $result.etw_lost_buffers -ne 0 -or
    $result.guest_frame_count -le 0 -or
    $result.presentmon_frame_count -le 0) {
    throw 'PGR2 FreshBoot capture failed focus, ETW-loss, or frame-sample gates.'
}
$hdd = Get-Content -LiteralPath $result.hdd_lifecycle -Raw | ConvertFrom-Json
if ($hdd.cleanup_status -cne 'complete' -or
    $hdd.seed_sha256_final -cne $identity.seed_hdd.sha256) {
    throw 'PGR2 FreshBoot HDD cleanup or immutable-seed check failed.'
}

$receipt = [ordered]@{
    schema_version = 1
    status = 'complete'
    role = $Role
    workload = 'PGR2-FRESH-START'
    renderer = $Renderer
    run_id = $RunId
    source = [ordered]@{
        commit = $SourceCommit.ToLowerInvariant()
        tree = $SourceTree.ToLowerInvariant()
    }
    inputs = $identity
    duration_seconds = $DurationSeconds
    warmup_seconds = $WarmupSeconds
    capture_evidence = $actualEvidence
    hdd_lifecycle = [System.IO.Path]::GetFullPath($result.hdd_lifecycle)
    completed_utc = [DateTime]::UtcNow.ToString('O')
}
Write-JsonAtomic (Join-Path $actualEvidence 'wrapper-identity.json') $receipt
$result
