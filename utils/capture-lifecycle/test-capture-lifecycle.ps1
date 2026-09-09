$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

. (Join-Path $PSScriptRoot 'capture-lifecycle.ps1')

function Assert-True {
    param([bool]$Condition, [string]$Message)

    if (-not $Condition) {
        throw "Assertion failed: $Message"
    }
}

function Assert-Throws {
    param([scriptblock]$Action, [string]$Message)

    try {
        & $Action
    } catch {
        return
    }
    throw "Expected failure: $Message"
}

function Write-TestControl {
    param(
        [string]$CellPath,
        [hashtable]$Control
    )

    $Control | ConvertTo-Json -Depth 4 |
        Set-Content -LiteralPath (Join-Path $CellPath 'control.json') -NoNewline
}

function New-RequiredCaptureFiles {
    param(
        [string]$CellPath,
        [string]$LaunchPath
    )

    foreach ($name in @('result.json', 'actions.jsonl', 'vulkan-perf.jsonl')) {
        [System.IO.File]::WriteAllText((Join-Path $CellPath $name), "synthetic $name")
    }
    foreach ($name in @(
            'stderr.log',
            'stdout.log',
            'guest-flips.log',
            'measurement-start.capture.json',
            'measurement-end.capture.json',
            'measurement-end.png')) {
        [System.IO.File]::WriteAllText((Join-Path $LaunchPath $name), "synthetic $name")
    }
}

$root = Join-Path ([System.IO.Path]::GetTempPath()) ("capture-lifecycle-" + [guid]::NewGuid().ToString('N'))

try {
    New-Item -ItemType Directory -Path $root | Out-Null

    Assert-CaptureProcessQueryIdle -ProcessQueryResult $null
    Assert-CaptureProcessQueryIdle -ProcessQueryResult @()
    Assert-Throws { Assert-CaptureProcessQueryIdle -ProcessQueryResult 'one' } 'singleton process query'
    Assert-Throws { Assert-CaptureProcessQueryIdle -ProcessQueryResult @('one', 'two') } 'multiple process query'

    $cell = Join-Path $root 'cell'
    $launch = Join-Path $cell 'launch-1'
    New-Item -ItemType Directory -Path $launch -Force | Out-Null
    New-RequiredCaptureFiles -CellPath $cell -LaunchPath $launch
    Assert-Throws { Resolve-CaptureLaunchArtifacts -CellPath $cell } 'missing control file'
    [System.IO.File]::WriteAllText((Join-Path $cell 'control.json'), 'not-json')
    Assert-Throws { Resolve-CaptureLaunchArtifacts -CellPath $cell } 'invalid control JSON'
    Write-TestControl -CellPath $cell -Control @{
        schema_version = 1
        status = 'closed'
        launches = 1
        launch_dir = [System.IO.Path]::GetFullPath($launch)
    }

    $resolved = Resolve-CaptureLaunchArtifacts -CellPath $cell
    Assert-True ($resolved.launch_dir -eq [System.IO.Path]::GetFullPath($launch)) 'canonical launch directory'
    Assert-True ($resolved.telemetry -eq (Join-Path $cell 'vulkan-perf.jsonl')) 'cell artifact resolves from cell root'
    Assert-True ($resolved.stderr -eq (Join-Path $launch 'stderr.log')) 'stderr resolves from launch directory'

    [System.IO.File]::WriteAllText((Join-Path $cell 'stderr.log'), 'stale cell stderr')
    Remove-Item -LiteralPath (Join-Path $launch 'stderr.log')
    Assert-Throws { Resolve-CaptureLaunchArtifacts -CellPath $cell } 'cell-root stderr must not mask missing launch stderr'
    [System.IO.File]::WriteAllText((Join-Path $launch 'stderr.log'), 'synthetic stderr')

    Write-TestControl -CellPath $cell -Control @{
        schema_version = 1
        status = 'open'
        launches = 1
        launch_dir = [System.IO.Path]::GetFullPath($launch)
    }
    Assert-Throws { Resolve-CaptureLaunchArtifacts -CellPath $cell } 'non-closed cell'

    Write-TestControl -CellPath $cell -Control @{
        schema_version = 1
        launches = 1
        launch_dir = [System.IO.Path]::GetFullPath($launch)
    }
    Assert-Throws { Resolve-CaptureLaunchArtifacts -CellPath $cell } 'missing cell status'

    Write-TestControl -CellPath $cell -Control @{
        schema_version = 2
        status = 'closed'
        launches = 1
        launch_dir = [System.IO.Path]::GetFullPath($launch)
    }
    Assert-Throws { Resolve-CaptureLaunchArtifacts -CellPath $cell } 'wrong schema version'

    Write-TestControl -CellPath $cell -Control @{
        schema_version = 1
        status = 'closed'
        launches = 2
        launch_dir = [System.IO.Path]::GetFullPath($launch)
    }
    Assert-Throws { Resolve-CaptureLaunchArtifacts -CellPath $cell } 'multiple launches'

    Write-TestControl -CellPath $cell -Control @{
        schema_version = 1
        status = 'closed'
        launches = 0
        launch_dir = [System.IO.Path]::GetFullPath($launch)
    }
    Assert-Throws { Resolve-CaptureLaunchArtifacts -CellPath $cell } 'zero launches'

    Write-TestControl -CellPath $cell -Control @{
        schema_version = 1
        status = 'closed'
        launches = 1
        launch_dir = 'missing-launch'
    }
    Assert-Throws { Resolve-CaptureLaunchArtifacts -CellPath $cell } 'wrong launch directory'

    Write-TestControl -CellPath $cell -Control @{
        schema_version = 1
        status = 'closed'
        launches = 1
    }
    Assert-Throws { Resolve-CaptureLaunchArtifacts -CellPath $cell } 'missing launch directory'

    Write-TestControl -CellPath $cell -Control @{
        schema_version = 1
        status = 'closed'
        launches = 1
        launch_dir = '../outside'
    }
    Assert-Throws { Resolve-CaptureLaunchArtifacts -CellPath $cell } 'outside launch directory'

    Remove-Item -LiteralPath (Join-Path $launch 'measurement-end.png')
    Write-TestControl -CellPath $cell -Control @{
        schema_version = 1
        status = 'closed'
        launches = 1
        launch_dir = [System.IO.Path]::GetFullPath($launch)
    }
    Assert-Throws { Resolve-CaptureLaunchArtifacts -CellPath $cell } 'missing required artifact'
    [System.IO.File]::WriteAllText((Join-Path $launch 'measurement-end.png'), 'synthetic image')

    $anchorPath = Join-Path $root 'before-anchor.json'
    Save-CaptureClockAnchor -AnchorPath $anchorPath -Phase 'before' -SourceIdentity @{ commit = 'synthetic-source' } -BinaryIdentity @{ sha256 = 'synthetic-binary' }
    $originalBytes = [System.IO.File]::ReadAllBytes($anchorPath)
    try {
        throw 'injected post-capture validation failure'
    } catch {
        # The already-persisted anchor must remain readable after this failure.
    }
    $anchor = Get-Content -LiteralPath $anchorPath -Raw | ConvertFrom-Json
    Assert-True ($anchor.type -eq 'capture_clock_anchor') 'anchor type'
    Assert-True ($anchor.qpc_before -le $anchor.qpc_after) 'QPC bracket order'
    Assert-True ($anchor.qpc_frequency_hz -gt 0) 'QPC frequency'
    Assert-True ($null -ne $anchor.utc_sample) 'UTC sample'
    Assert-True ($null -ne $anchor.clock_source) 'clock source metadata'
    Assert-True ($anchor.source_identity.commit -eq 'synthetic-source') 'source identity'
    Assert-Throws {
        Save-CaptureClockAnchor -AnchorPath $anchorPath -Phase 'after' -SourceIdentity @{ commit = 'replacement' } -BinaryIdentity @{ sha256 = 'replacement' }
    } 'repeat anchor path'
    $repeatBytes = [System.IO.File]::ReadAllBytes($anchorPath)
    Assert-True ([Convert]::ToBase64String($originalBytes) -eq [Convert]::ToBase64String($repeatBytes)) 'anchor must not be overwritten'

    Write-Output 'capture-lifecycle controls passed'
} finally {
    if (Test-Path -LiteralPath $root) {
        Remove-Item -LiteralPath $root -Recurse -Force
    }
}
