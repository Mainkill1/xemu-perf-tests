$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw "Assertion failed: $Message" }
}

function Get-Sha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

$root = Join-Path ([System.IO.Path]::GetTempPath()) (
    'pgr2-fresh-start-' + [guid]::NewGuid().ToString('N'))
$runner = Join-Path $PSScriptRoot 'run-pgr2-fresh-start.ps1'
$powerShell = (Get-Process -Id $PID).Path
try {
    New-Item -ItemType Directory -Path $root | Out-Null
    $suite = Join-Path $root 'suite'
    $captureRoot = Join-Path $root 'captures'
    New-Item -ItemType Directory -Path $suite, $captureRoot | Out-Null
    $xemu = Join-Path $root 'xemu.exe'
    $disc = Join-Path $root 'pgr2.iso'
    $seed = Join-Path $root 'seed.qcow2'
    $config = Join-Path $root 'vulkan.toml'
    $launcher = Join-Path $suite 'start-retail-snapshot.ps1'
    $capture = Join-Path $suite 'fake-capture.ps1'
    foreach ($item in @($xemu, $disc, $seed, $config, $launcher)) {
        [System.IO.File]::WriteAllText($item, "synthetic $item")
    }
    @'
param(
    [string]$Xemu, [string]$SeedHdd, [string]$BaseConfig,
    [string]$LaunchMode, [string]$Snapshot, [string]$Game,
    [string]$Disc, [string]$CaptureRoot, [string]$BuildResultName,
    [string]$Mode, [string]$Renderer, [int]$SurfaceScale,
    [int]$DurationSeconds, [int]$WarmupSeconds,
    [string]$TraceProfile, [string]$TraceStartMode,
    [string]$VkTelemetry, [string]$PresentMonMode, [string]$RunId
)
$runPath = Join-Path $CaptureRoot $RunId
New-Item -ItemType Directory -Path $runPath | Out-Null
[ordered]@{
    cleanup_status = 'complete'
    seed_sha256_final = (Get-FileHash -LiteralPath $SeedHdd -Algorithm SHA256).Hash.ToLowerInvariant()
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runPath 'hdd.json')
[pscustomobject][ordered]@{
    status = 'complete'; functional_status = 'complete'
    measurement_status = 'complete'; launch_mode = $LaunchMode
    renderer = $Renderer
    xemu_sha256 = (Get-FileHash -LiteralPath $Xemu -Algorithm SHA256).Hash.ToLowerInvariant()
    evidence = $runPath; hdd_lifecycle = (Join-Path $runPath 'hdd.json')
    focus_loss_samples = 0; etw_lost_events = 0; etw_lost_buffers = 0
    guest_frame_count = 10; presentmon_frame_count = 10
}
'@ | Set-Content -LiteralPath $capture -Encoding utf8

    $arguments = @(
        '-NoProfile', '-File', $runner,
        '-Role', 'baseline', '-Xemu', $xemu,
        '-ExpectedXemuSha256', (Get-Sha256 $xemu),
        '-SourceCommit', ('1' * 40), '-SourceTree', ('2' * 40),
        '-Renderer', 'VULKAN', '-Disc', $disc,
        '-ExpectedDiscSha256', (Get-Sha256 $disc),
        '-SeedHdd', $seed, '-ExpectedSeedSha256', (Get-Sha256 $seed),
        '-BaseConfig', $config,
        '-ExpectedBaseConfigSha256', (Get-Sha256 $config),
        '-CaptureRunner', $capture,
        '-ExpectedCaptureRunnerSha256', (Get-Sha256 $capture),
        '-Launcher', $launcher,
        '-ExpectedLauncherSha256', (Get-Sha256 $launcher),
        '-CaptureRoot', $captureRoot, '-RunId', 'success',
        '-DurationSeconds', '10', '-WarmupSeconds', '3')
    & $powerShell @arguments | Out-Null
    Assert-True ($LASTEXITCODE -eq 0) 'synthetic capture exits zero'
    $receipt = Get-Content -LiteralPath (
        Join-Path $captureRoot 'success\wrapper-identity.json') -Raw |
        ConvertFrom-Json
    Assert-True ($receipt.role -eq 'baseline') 'role is durable'
    Assert-True ($receipt.renderer -eq 'VULKAN') 'renderer is durable'
    Assert-True ($receipt.inputs.xemu.sha256 -eq (Get-Sha256 $xemu)) `
        'executable identity is durable'

    $bad = @($arguments)
    $hashIndex = [array]::IndexOf($bad, '-ExpectedXemuSha256') + 1
    $bad[$hashIndex] = '0' * 64
    $runIndex = [array]::IndexOf($bad, '-RunId') + 1
    $bad[$runIndex] = 'bad-hash'
    & $powerShell @bad 2>$null | Out-Null
    Assert-True ($LASTEXITCODE -ne 0) 'identity mismatch exits nonzero'
    Assert-True (-not (Test-Path -LiteralPath (
                Join-Path $captureRoot 'bad-hash'))) `
        'identity mismatch starts no capture'

    Write-Output 'PGR2 fresh-start controls passed'
} finally {
    if (Test-Path -LiteralPath $root) {
        Remove-Item -LiteralPath $root -Recurse -Force
    }
}
