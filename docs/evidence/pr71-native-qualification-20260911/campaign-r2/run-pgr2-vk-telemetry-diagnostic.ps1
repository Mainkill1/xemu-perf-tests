<#
.SYNOPSIS
Runs a separate low-footprint PGR2 snapshot telemetry pair for Hybrid Off/On.
.DESCRIPTION
This diagnostic is isolated from the qualification ResultsRoot. It uses the
exact staged candidate executable, Vulkan telemetry, two run-local profiles,
and no ETW trace. It records pipeline_prepare CPU time beside Vulkan stall
waits, then emits a sanitized pair comparison. It must be run only after the
active qualification campaign has completed.
#>
[CmdletBinding()]
param(
    [string]$DiagnosticRoot = '',
    [string]$BuildOverrideRoot = '',
    [ValidateRange(15, 120)][int]$DurationSeconds = 30,
    [switch]$AllowStoppedRetailCampaign
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Campaign = & (Join-Path $PSScriptRoot 'campaign-config.ps1')
. (Join-Path $PSScriptRoot 'campaign-common.ps1')
Assert-NoPlaceholders $Campaign 'PR71 diagnostic campaign'
$campaignManifest = Join-Path $Campaign.ResultsRoot 'campaign-manifest.json'
if (-not (Test-Path -LiteralPath $campaignManifest -PathType Leaf)) {
    throw 'The active qualification campaign has no completion manifest; defer this diagnostic.'
}
$campaignState = Get-Content -LiteralPath $campaignManifest -Raw | ConvertFrom-Json
if ($campaignState.status -ne 'passed') {
    # This mode is diagnostic only. A stopped qualification campaign never
    # acquires a passing result from the separate telemetry capture.
    $retailManifestPath = Join-Path $Campaign.ResultsRoot 'retail\campaign.json'
    if (-not $AllowStoppedRetailCampaign -or $campaignState.status -ne 'failed' -or
        -not (Test-Path -LiteralPath $retailManifestPath -PathType Leaf)) {
        throw "Qualification incomplete (status $($campaignState.status)); diagnostic requires an explicitly stopped, cleaned campaign."
    }
    $retailState = Get-Content -LiteralPath $retailManifestPath -Raw | ConvertFrom-Json
    $snapshotCells = @(Get-ChildItem -LiteralPath (Join-Path $Campaign.ResultsRoot 'retail\cells') `
        -Filter '*pgr2_snapshot*.json' -File)
    $badSnapshotCells = @($snapshotCells | Where-Object {
        (Get-Content -LiteralPath $_.FullName -Raw | ConvertFrom-Json).status -ne 'passed'
    })
    $xisoPassed = @($campaignState.phases | Where-Object {
        $_.name -eq 'full_xiso_157' -and $_.status -eq 'passed'
    }).Count -eq 1
    if (-not $xisoPassed -or $retailState.final_cleanup.status -ne 'passed' -or
        $snapshotCells.Count -ne 13 -or $badSnapshotCells.Count -ne 0) {
        throw 'Stopped campaign lacks clean full-XISO and 13 completed PGR2 snapshot cells.'
    }
}

$diagRoot = if ($DiagnosticRoot) {
    [IO.Path]::GetFullPath($DiagnosticRoot)
} else {
    Join-Path (Split-Path -Parent $Campaign.ResultsRoot) `
        'pr71-native-diagnostic-pgr2-vk-telemetry'
}
$qualificationRoot = [IO.Path]::GetFullPath($Campaign.ResultsRoot)
if ($diagRoot.StartsWith($qualificationRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'DiagnosticRoot must be outside the active qualification ResultsRoot.'
}
if (Test-Path -LiteralPath $diagRoot) {
    throw "Refusing to overwrite diagnostic evidence: $diagRoot"
}
New-Item -ItemType Directory -Path $diagRoot -Force | Out-Null

function Resolve-DiagnosticBuild {
    if (-not $hasBuildOverride) {
        return $Campaign.Builds.candidate
    }
    $overrideRoot = [IO.Path]::GetFullPath($BuildOverrideRoot)
    if ($overrideRoot.StartsWith(
            [IO.Path]::GetFullPath($Campaign.ResultsRoot),
            [StringComparison]::OrdinalIgnoreCase)) {
        throw 'BuildOverrideRoot must be outside the active qualification ResultsRoot.'
    }
    $overrideExe = Join-Path $overrideRoot 'xemu.exe'
    $overrideInfoPath = Join-Path $overrideRoot 'BUILD_INFO.txt'
    foreach ($path in @($overrideExe, $overrideInfoPath)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Build override is missing required artifact: $path"
        }
    }
    $info = Read-BuildInfo $overrideInfoPath
    foreach ($name in @('SOURCE_SHA', 'SOURCE_TREE', 'XEMU_SHA256', 'SOURCE_STATE')) {
        if (-not $info.Contains($name) -or [string]::IsNullOrWhiteSpace([string]$info[$name])) {
            throw "Build override BUILD_INFO lacks required $name"
        }
    }
    if ($info.SOURCE_SHA -notmatch '^[0-9a-f]{40}$' -or
        $info.SOURCE_TREE -notmatch '^[0-9a-f]{40}$' -or
        $info.XEMU_SHA256 -notmatch '^[0-9a-f]{64}$') {
        throw 'Build override BUILD_INFO has malformed source/tree/executable identity.'
    }
    if ($info.SOURCE_STATE -ne 'diagnostic') {
        throw "Build override SOURCE_STATE must be diagnostic, observed '$($info.SOURCE_STATE)'."
    }
    foreach ($name in @('QUALIFICATION_STATUS', 'RELEASE_STATUS', 'RELEASE_QUALIFIED', 'CLASSIFICATION')) {
        if ($info.Contains($name) -and [string]$info[$name] -match '(?i)release|qualif|pass') {
            throw "Build override has release-qualified status in BUILD_INFO: $name=$($info[$name])"
        }
    }
    if ($info.Contains('LOGICAL_COMMIT') -and
        $info.LOGICAL_COMMIT -ne $Campaign.Builds.candidate.LogicalCommit) {
        throw 'Build override logical commit does not match the PR71 candidate.'
    }
    $actualHash = Get-Sha256 $overrideExe
    if ($actualHash -ne $info.XEMU_SHA256) {
        throw "Build override executable hash mismatch: expected $($info.XEMU_SHA256), observed $actualHash"
    }
    [ordered]@{
        Role = 'candidate'
        LogicalCommit = $Campaign.Builds.candidate.LogicalCommit
        SourceCommit = $info.SOURCE_SHA
        Tree = $info.SOURCE_TREE
        Xemu = $overrideExe
        XemuSha256 = $info.XEMU_SHA256
        BuildInfo = $overrideInfoPath
        SourceState = 'diagnostic'
        OverrideRoot = $overrideRoot
    }
}

$hasBuildOverride = -not [string]::IsNullOrWhiteSpace($BuildOverrideRoot)
$build = Resolve-DiagnosticBuild
$buildReceipt = Assert-BuildContract $build
$buildReceipt.build_source_state = if ($hasBuildOverride) { 'diagnostic' } else { 'staged-candidate' }
$buildReceipt.build_override = $hasBuildOverride
$capture = Join-Path $PSScriptRoot 'capture-pgr2-native-pr71.ps1'
$analyzer = Join-Path $PSScriptRoot 'compare-pgr2-vk-telemetry.py'
$python = $Campaign.Xiso.Python
$diagCampaign = [ordered]@{
    ResultsRoot = $diagRoot
    Host = $Campaign.Host
}
$cells = @()
$summaryPaths = [ordered]@{}

function New-DiagnosticProfile([string]$Name, [string]$Hybrid) {
    $directory = Join-Path $diagRoot "profiles\$Name"
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
    $xemu = Join-Path $directory 'xemu.exe'
    $buildInfo = Join-Path $directory 'BUILD_INFO.txt'
    Copy-Item -LiteralPath $build.Xemu -Destination $xemu
    Copy-Item -LiteralPath $build.BuildInfo -Destination $buildInfo
    Assert-Hash $xemu $build.XemuSha256 "$Name diagnostic executable"
    [ordered]@{
        directory = $directory
        xemu = $xemu
        build_info = $buildInfo
        profile_root = Join-Path $directory 'profile-env'
        hybrid = $Hybrid
        shader_cache = 'Enabled'
    }
}

try {
    Assert-HostIdle $diagCampaign 'diagnostic start'
    foreach ($hybrid in @('Off', 'On')) {
        $slug = $hybrid.ToLowerInvariant()
        $profile = New-DiagnosticProfile "candidate-vulkan-hybrid-$slug" $hybrid
        $runRoot = Join-Path $diagRoot "runs\hybrid-$slug"
        $privateHdd = Join-Path $runRoot 'hybrid-pgr2-result\private-hdd.qcow2'
        $failure = $null
        try {
            $raw = & $capture `
                -Xemu $profile.xemu `
                -SeedHdd $Campaign.Retail.Pgr2SnapshotSeed `
                -BaseConfig $Campaign.Retail.Pgr2VulkanConfig `
                -LaunchMode Snapshot `
                -Snapshot $Campaign.Retail.Pgr2Snapshot `
                -Game PGR2 `
                -Disc $Campaign.Retail.Pgr2Disc `
                -CaptureRoot $runRoot `
                -BuildResultName "hybrid-$slug-result.json" `
                -Mode 'PGR2-HYBRID-VK-TELEMETRY-DIAGNOSTIC' `
                -Renderer VULKAN `
                -ShaderCache Enabled `
                -HybridUbershaders $hybrid `
                -SurfaceScale 1 `
                -DurationSeconds $DurationSeconds `
                -WarmupSeconds 3 `
                -TraceProfile None `
                -TraceStartMode SteadyState `
                -VkTelemetry Enabled `
                -PresentMonMode Disabled `
                -RunId "hybrid-$slug" `
                -ProfileRoot $profile.profile_root
            if ($raw.status -ne 'complete' -or
                $raw.xemu_sha256 -ne $build.XemuSha256 -or
                $raw.renderer -ne 'VULKAN' -or
                $raw.vk_telemetry_active -ne $true -or
                -not $raw.vk_perf_summary) {
                throw "Hybrid $hybrid telemetry capture admission failed"
            }
            $summaryPaths[$slug] = $raw.vk_perf_summary
            $cells += [ordered]@{
                hybrid_ubershaders = $hybrid
                shader_cache = 'Enabled'
                renderer = 'vulkan'
                role = $build.Role
                logical_commit = $build.LogicalCommit
                source_commit = $build.SourceCommit
                source_tree = $build.Tree
                xemu_sha256 = $build.XemuSha256
                source_state = $buildReceipt.build_source_state
                build_override = $hasBuildOverride
                xemu_config_sha256 = $raw.xemu_config_sha256
                vk_perf_summary = Split-Path -Leaf $raw.vk_perf_summary
                vk_perf_measured = Split-Path -Leaf $raw.vk_perf_measured
                guest_frames = $raw.guest_frame_count
                guest_frame_p99_ms = $raw.guest_frame_p99_ms
                evidence = "runs/hybrid-$slug"
                status = 'passed'
            }
        } catch {
            $failure = $_.Exception
        } finally {
            $cleanup = Invoke-CampaignCleanup $diagCampaign "diagnostic hybrid $hybrid" @($privateHdd)
        }
        if ($cleanup.status -ne 'passed') {
            $message = $cleanup.errors -join '; '
            if ($failure) { throw "$($failure.Message); cleanup failed: $message" }
            throw "Hybrid $hybrid cleanup failed: $message"
        }
        if ($failure) { throw $failure }
    }

    if (-not $summaryPaths.off -or -not $summaryPaths.on) {
        throw 'Both Hybrid Off and On telemetry summaries are required.'
    }
    $comparison = Join-Path $diagRoot 'pgr2-vk-telemetry-comparison.json'
    & $python $analyzer --off-summary $summaryPaths.off --on-summary $summaryPaths.on `
        --output $comparison | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Telemetry pair comparison failed.' }
    [ordered]@{
        schema_version = 1
        status = 'passed'
        diagnostic_only = $true
        campaign_id = $Campaign.CampaignId
        workload = 'pgr2_snapshot'
        renderer = 'vulkan'
        telemetry = 'XEMU_VK_PERF_LOG'
        cache_shaders = 'Enabled'
        candidate = $buildReceipt
        build_override = $hasBuildOverride
        build_source_state = $buildReceipt.build_source_state
        cells = $cells
        comparison = 'pgr2-vk-telemetry-comparison.json'
        comparison_markdown = 'pgr2-vk-telemetry-comparison.md'
        raw_paths = 'Run-local paths are intentionally omitted; see each cell evidence directory.'
        cleanup = 'Each cell invokes automated xemu/trace/HDD cleanup.'
    } | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $diagRoot 'diagnostic-receipt.json') -Encoding utf8
} finally {
    $cleanup = Invoke-CampaignCleanup $diagCampaign 'diagnostic final'
    if ($cleanup.status -ne 'passed') { throw ($cleanup.errors -join '; ') }
}

Write-Output (Join-Path $diagRoot 'diagnostic-receipt.json')
