$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Campaign = & (Join-Path $PSScriptRoot 'campaign-config.ps1')
. (Join-Path $PSScriptRoot 'campaign-common.ps1')

Assert-NoPlaceholders $Campaign 'PR71 campaign'
$buildReceipts = @()
foreach ($role in @('fixed_baseline', 'previous_main', 'candidate')) {
    $buildReceipts += Assert-BuildContract $Campaign.Builds[$role]
}
$root = Join-Path $Campaign.ResultsRoot 'retail'
$capture = Join-Path $PSScriptRoot 'capture-pgr2-native-pr71.ps1'
$morrowindCellRunner = Join-Path $PSScriptRoot 'run-morrowind-qualification-cell-exact-isolated.ps1'

function Invoke-Pgr2Cell(
    [string]$Label,
    [string]$Workload,
    [System.Collections.IDictionary]$Build,
    [System.Collections.IDictionary]$Portable,
    [ValidateSet('OPENGL', 'VULKAN')][string]$Renderer,
    [ValidateSet('Snapshot', 'FreshBoot')][string]$LaunchMode,
    [ValidateSet('none', 'cold', 'warm')][string]$CachePhase,
    [ValidateSet('Off', 'On')][string]$HybridUbershaders = 'Off',
    [ValidateSet('baseline-candidate', 'candidate-baseline')][string]$RunOrder = 'baseline-candidate'
) {
    Assert-HostIdle $Campaign "before $Label"
    $cacheBefore = Get-SpirvCacheReceipt $Portable.directory
    if ($Renderer -eq 'OPENGL' -and $cacheBefore) {
        throw "$Label OpenGL profile contains a Vulkan cache"
    }
    if ($CachePhase -eq 'cold' -and $cacheBefore) { throw "$Label was not cold" }
    if ($CachePhase -eq 'warm' -and -not $cacheBefore) { throw "$Label has no cold seed" }

    $seed = if ($LaunchMode -eq 'Snapshot') {
        $Campaign.Retail.Pgr2SnapshotSeed
    } else { $Campaign.Retail.Pgr2FreshSeed }
    $config = if ($Renderer -eq 'VULKAN') {
        $Campaign.Retail.Pgr2VulkanConfig
    } else { $Campaign.Retail.Pgr2OpenGlConfig }
    $runRoot = Join-Path $root "runs\$Workload"
    $cellPrivateHdd = Join-Path $runRoot "$Label\private-hdd.qcow2"
    $result = $null
    $failure = $null
    $cleanup = $null
    try {
        $parameters = @{
            Xemu = $Portable.xemu
            SeedHdd = $seed
            BaseConfig = $config
            LaunchMode = $LaunchMode
            Snapshot = if ($LaunchMode -eq 'Snapshot') {
                $Campaign.Retail.Pgr2Snapshot
            } else { '' }
            Game = 'PGR2'
            Disc = $Campaign.Retail.Pgr2Disc
            CaptureRoot = $runRoot
            BuildResultName = "$Label-result.json"
            Mode = if ($LaunchMode -eq 'Snapshot') {
                'PGR2-LAG-V2-SNAPSHOT'
            } else { 'PGR2-FRESH-START-2MIN' }
            Renderer = $Renderer
            SurfaceScale = 1
            DurationSeconds = if ($LaunchMode -eq 'Snapshot') {
                $Campaign.Retail.Pgr2SnapshotDurationSeconds
            } else { $Campaign.Retail.Pgr2FreshBootDurationSeconds }
            WarmupSeconds = if ($LaunchMode -eq 'Snapshot') {
                $Campaign.Retail.Pgr2SnapshotWarmupSeconds
            } else { $Campaign.Retail.Pgr2FreshBootWarmupSeconds }
            TraceProfile = 'None'
            TraceStartMode = 'SteadyState'
            VkTelemetry = 'Disabled'
            PresentMonMode = 'Enabled'
            RunId = $Label
            ProfileRoot = $Portable.profile_root
            ShaderCache = $Portable.shader_cache
            HybridUbershaders = $HybridUbershaders
        }
        if ($LaunchMode -eq 'Snapshot') {
            $parameters.SnapshotKeySequence = @('B-3')
        }
        if ($CachePhase -ne 'none') { $parameters.RequireSpirvSummary = $true }

        $raw = & $capture @parameters
        if ($raw.status -ne 'complete' -or
            $raw.functional_status -ne 'complete' -or
            $raw.measurement_status -ne 'complete' -or
            $raw.xemu_sha256 -ne $Build.XemuSha256 -or
            $raw.focus_loss_samples -ne 0 -or
            $raw.not_responding_samples -ne 0 -or
            $raw.guest_frame_count -le 0 -or
            $raw.presentmon_frame_count -le 0) {
            throw "$Label gameplay/measurement admission failed"
        }
        $hdd = Get-Content -LiteralPath $raw.hdd_lifecycle -Raw | ConvertFrom-Json
        if ($hdd.cleanup_status -ne 'complete' -or
            (Test-Path -LiteralPath $hdd.private_path)) {
            throw "$Label private HDD cleanup failed"
        }
        $shutdown = Get-Content -LiteralPath $raw.graceful_shutdown -Raw | ConvertFrom-Json
        if (-not $shutdown.requested -or -not $shutdown.exited) {
            throw "$Label did not close normally"
        }

        $cacheAfter = Get-SpirvCacheReceipt $Portable.directory
        $adapterEvidence = Get-AdapterEvidence ($Renderer.ToLowerInvariant()) `
            $raw.launch_stderr $Campaign.Host.ExpectedAutoAdapterVendor
        $stats = if ($Build.Role -eq 'candidate' -and $Renderer -eq 'VULKAN') {
            Get-SpirvStats $raw.launch_stderr
        } else { $null }
        Assert-CachePhase $CachePhase $cacheBefore $cacheAfter $stats

        $result = [ordered]@{
            label = $Label
            workload = $Workload
            launch_mode = $LaunchMode
            role = $Build.Role
            logical_commit = $Build.LogicalCommit
            source_commit = $Build.SourceCommit
            tree = $Build.Tree
            xemu_sha256 = $Build.XemuSha256
            build_info_sha256 = Get-Sha256 $Portable.BuildInfo
            xemu_config_sha256 = $raw.xemu_config_sha256
            base_config_sha256 = $raw.base_config_sha256
            launch_config_sha256 = $raw.launch_config_sha256
            renderer = $Renderer.ToLowerInvariant()
            gpu_policy = $Campaign.Host.GpuPolicy
            expected_auto_adapter_vendor = $Campaign.Host.ExpectedAutoAdapterVendor
            adapter_evidence = $adapterEvidence
            cache_phase = $CachePhase
            shader_cache = $Portable.shader_cache
            hybrid_ubershaders = $HybridUbershaders
            run_order = $RunOrder
            cache_before = $cacheBefore
            cache_after = $cacheAfter
            cache_stats = $stats
            metrics = [ordered]@{
                fps = $raw.average_fps
                frame_average_ms = $raw.guest_frame_average_ms
                p95_ms = $raw.guest_frame_p95_ms
                p99_ms = $raw.guest_frame_p99_ms
                max_ms = $raw.guest_frame_max_ms
                stalls = $raw.guest_frame_stall_count
                guest_frames = $raw.guest_frame_count
                guest_flips = $raw.guest_flip_frame_count
                host_presents = $raw.presentmon_frame_count
                host_average_ms = $raw.host_present_average_ms
                host_p95_ms = $raw.host_present_p95_ms
                host_p99_ms = $raw.host_present_p99_ms
                host_max_ms = $raw.host_present_max_ms
            }
            evidence = $raw.evidence
            screenshot = $raw.screenshot
            gpu_csv = $raw.gpu_csv
            normal_close = $true
            private_hdd_deleted = $true
            seed_sha256 = $hdd.seed_sha256_final
            status = 'passed'
            cleanup = $null
        }
    } catch { $failure = $_.Exception } finally {
        $cleanup = Invoke-CampaignCleanup $Campaign $Label @($cellPrivateHdd)
    }
    if ($cleanup.status -ne 'passed') {
        $message = $cleanup.errors -join '; '
        if ($failure) { throw "$($failure.Message); cleanup failed: $message" }
        throw "$Label cleanup failed: $message"
    }
    if ($failure) { throw $failure }
    $result.cleanup = $cleanup
    Write-JsonAtomic (Join-Path $root "cells\$Label.json") $result
    [pscustomobject]$result
}

function Invoke-MorrowindCell(
    [string]$Label,
    [System.Collections.IDictionary]$Build,
    [System.Collections.IDictionary]$Portable,
    [ValidateSet('OPENGL', 'VULKAN')][string]$Renderer,
    [ValidateSet('none', 'cold', 'warm')][string]$CachePhase,
    [ValidateSet('Off', 'On')][string]$HybridUbershaders = 'Off',
    [ValidateSet('baseline-candidate', 'candidate-baseline')][string]$RunOrder = 'baseline-candidate'
) {
    Assert-HostIdle $Campaign "before $Label"
    $cacheBefore = Get-SpirvCacheReceipt $Portable.directory
    if ($Renderer -eq 'OPENGL' -and $cacheBefore) {
        throw "$Label OpenGL profile contains a Vulkan cache"
    }
    if ($CachePhase -eq 'cold' -and $cacheBefore) { throw "$Label was not cold" }
    if ($CachePhase -eq 'warm' -and -not $cacheBefore) { throw "$Label has no cold seed" }
    $runDirectory = Join-Path $root "runs\morrowind_snapshot\$Label"
    $privateHdd = Join-Path $runDirectory 'private-hdd.qcow2'
    $result = $null
    $failure = $null
    $cleanup = $null
    try {
        $rawText = & $morrowindCellRunner -Root $runDirectory -Role $Build.Role `
            -Xemu $Portable.xemu -XemuSha256 $Build.XemuSha256 `
            -SourceCommit $Build.SourceCommit -SourceTree $Build.Tree `
            -Renderer $Renderer `
            -SeedHdd $Campaign.Retail.MorrowindSeed `
            -DurationSeconds $Campaign.Retail.MorrowindDurationSeconds `
            -ConfigSource $(if ($Renderer -eq 'VULKAN') { Join-Path $Campaign.Retail.MorrowindConfigRoot 'vulkan.toml' } else { Join-Path $Campaign.Retail.MorrowindConfigRoot 'opengl.toml' }) `
            -ShaderCache $Portable.shader_cache `
            -HybridUbershaders $HybridUbershaders `
            -Disc $Campaign.Retail.MorrowindDisc
        $raw = $rawText | ConvertFrom-Json
        if ($raw.status -ne 'complete' -or -not $raw.private_hdd_deleted -or
            $raw.executable_sha256 -ne $Build.XemuSha256 -or
            $raw.source_commit -ne $Build.SourceCommit -or
            $raw.source_tree -ne $Build.Tree -or
            $raw.gameplay_admission -notmatch '^PASSED') {
            throw "$Label Morrowind admission failed"
        }
        $control = Get-Content -LiteralPath (Join-Path $runDirectory 'control.json') `
            -Raw | ConvertFrom-Json
        if ($control.status -ne 'closed') { throw "$Label did not close normally" }
        $launchConfig = Join-Path $control.launch_dir 'launch-config.toml'

        $cacheAfter = Get-SpirvCacheReceipt $Portable.directory
        $stderr = Join-Path $runDirectory 'launch-1\stderr.log'
        $adapterEvidence = Get-AdapterEvidence ($Renderer.ToLowerInvariant()) `
            $stderr $Campaign.Host.ExpectedAutoAdapterVendor
        $stats = if ($Build.Role -eq 'candidate' -and $Renderer -eq 'VULKAN') {
            Get-SpirvStats $stderr
        } else { $null }
        Assert-CachePhase $CachePhase $cacheBefore $cacheAfter $stats

        $result = [ordered]@{
            label = $Label
            workload = 'morrowind_snapshot'
            launch_mode = 'Snapshot'
            role = $Build.Role
            logical_commit = $Build.LogicalCommit
            source_commit = $Build.SourceCommit
            tree = $Build.Tree
            xemu_sha256 = $Build.XemuSha256
            build_info_sha256 = Get-Sha256 $Portable.BuildInfo
            xemu_config_sha256 = Get-Sha256 $launchConfig
            launch_config_sha256 = Get-Sha256 $launchConfig
            renderer = $Renderer.ToLowerInvariant()
            gpu_policy = $Campaign.Host.GpuPolicy
            expected_auto_adapter_vendor = $Campaign.Host.ExpectedAutoAdapterVendor
            adapter_evidence = $adapterEvidence
            cache_phase = $CachePhase
            shader_cache = $Portable.shader_cache
            hybrid_ubershaders = $HybridUbershaders
            run_order = $RunOrder
            cache_before = $cacheBefore
            cache_after = $cacheAfter
            cache_stats = $stats
            metrics = [ordered]@{
                fps = $raw.average_fps_proxy
                frame_average_ms = $raw.frame_interval_average_ms
                p95_ms = $raw.frame_interval_p95_ms
                p99_ms = $raw.frame_interval_p99_ms
                max_ms = $raw.frame_interval_max_ms
                stalls = $raw.frame_stall_count
                guest_frames = $raw.display_write_intervals
                elapsed_seconds = $raw.measurement_elapsed_seconds
            }
            metric_qualification = $raw.metric
            gameplay_admission = $raw.gameplay_admission
            evidence = $runDirectory
            screenshot_start = Join-Path $runDirectory 'launch-1\measurement-start.png'
            screenshot_end = Join-Path $runDirectory 'launch-1\measurement-end.png'
            normal_close = $true
            private_hdd_deleted = $raw.private_hdd_deleted
            seed_sha256 = $raw.seed_sha256_after
            status = 'passed'
            cleanup = $null
        }
    } catch { $failure = $_.Exception } finally {
        $cleanup = Invoke-CampaignCleanup $Campaign $Label @($privateHdd)
    }
    if ($cleanup.status -ne 'passed') {
        $message = $cleanup.errors -join '; '
        if ($failure) { throw "$($failure.Message); cleanup failed: $message" }
        throw "$Label cleanup failed: $message"
    }
    if ($failure) { throw $failure }
    $result.cleanup = $cleanup
    Write-JsonAtomic (Join-Path $root "cells\$Label.json") $result
    [pscustomobject]$result
}

function New-WorkloadPortables(
    [string]$Workload,
    [string]$OpenGlConfig,
    [string]$VulkanConfig
) {
    $portables = [ordered]@{}
    foreach ($role in @('fixed_baseline', 'previous_main', 'candidate')) {
        $portables["$role-opengl"] = New-PortableBuild $Campaign `
            $Campaign.Builds[$role] "$Workload-$role-opengl" $OpenGlConfig 'Enabled' 'Off'
        $portables["$role-vulkan"] = New-PortableBuild $Campaign `
            $Campaign.Builds[$role] "$Workload-$role-vulkan" $VulkanConfig 'Enabled' 'Off'
    }
    # Separate profiles make each cold/warm pair deterministic and retain the
    # cache artifact produced by each ubershader setting.
    $portables['candidate-vulkan-r2'] = New-PortableBuild $Campaign `
        $Campaign.Builds.candidate "$Workload-candidate-vulkan-r2" $VulkanConfig 'Enabled' 'Off'
    $portables['candidate-vulkan-on'] = New-PortableBuild $Campaign `
        $Campaign.Builds.candidate "$Workload-candidate-vulkan-on" $VulkanConfig 'Enabled' 'On'
    $portables['candidate-vulkan-on-r2'] = New-PortableBuild $Campaign `
        $Campaign.Builds.candidate "$Workload-candidate-vulkan-on-r2" $VulkanConfig 'Enabled' 'On'
    $portables
}

function Invoke-Pgr2Workload(
    [string]$Workload,
    [ValidateSet('Snapshot', 'FreshBoot')][string]$LaunchMode,
    [int]$OrdinalBase
) {
    $p = New-WorkloadPortables $Workload $Campaign.Retail.Pgr2OpenGlConfig `
        $Campaign.Retail.Pgr2VulkanConfig
    $rows = @()
    $matrix = @(
        @('baseline-opengl', 'fixed_baseline', 'OPENGL', 'none', 'fixed_baseline-opengl'),
        @('candidate-opengl', 'candidate', 'OPENGL', 'none', 'candidate-opengl'),
        @('previous-opengl', 'previous_main', 'OPENGL', 'none', 'previous_main-opengl'),
        @('baseline-vulkan-b1', 'fixed_baseline', 'VULKAN', 'none', 'fixed_baseline-vulkan'),
        @('candidate-vulkan-off-cold-r1', 'candidate', 'VULKAN', 'cold', 'candidate-vulkan', 'Off', 'baseline-candidate'),
        @('candidate-vulkan-off-warm-r1', 'candidate', 'VULKAN', 'warm', 'candidate-vulkan', 'Off', 'candidate-baseline'),
        @('previous-vulkan-b1', 'previous_main', 'VULKAN', 'none', 'previous_main-vulkan'),
        @('candidate-vulkan-off-cold-r2', 'candidate', 'VULKAN', 'cold', 'candidate-vulkan-r2', 'Off', 'baseline-candidate'),
        @('candidate-vulkan-on-cold-r1', 'candidate', 'VULKAN', 'cold', 'candidate-vulkan-on', 'On', 'candidate-baseline'),
        @('candidate-vulkan-on-warm-r1', 'candidate', 'VULKAN', 'warm', 'candidate-vulkan-on', 'On', 'baseline-candidate'),
        @('candidate-vulkan-on-cold-r2', 'candidate', 'VULKAN', 'cold', 'candidate-vulkan-on-r2', 'On', 'candidate-baseline'),
        @('baseline-vulkan-b2', 'fixed_baseline', 'VULKAN', 'none', 'fixed_baseline-vulkan'),
        @('previous-vulkan-b2', 'previous_main', 'VULKAN', 'none', 'previous_main-vulkan')
    )
    for ($index = 0; $index -lt $matrix.Count; $index++) {
        $entry = $matrix[$index]
        $label = '{0:D2}-{1}-{2}' -f ($OrdinalBase + $index), $Workload, $entry[0]
        $rows += Invoke-Pgr2Cell $label $Workload $Campaign.Builds[$entry[1]] `
            $p[$entry[4]] `
            $entry[2] $LaunchMode $entry[3] `
            $(if ($entry.Count -gt 5) { $entry[5] } else { 'Off' }) `
            $(if ($entry.Count -gt 6) { $entry[6] } else { 'baseline-candidate' })
    }
    $rows
}

function Invoke-MorrowindWorkload([int]$OrdinalBase) {
    $configRoot = $Campaign.Retail.MorrowindConfigRoot
    $openGlConfig = Join-Path $configRoot 'opengl.toml'
    $vulkanConfig = Join-Path $configRoot 'vulkan.toml'
    Assert-AutoGpuConfig $openGlConfig
    Assert-AutoGpuConfig $vulkanConfig
    $p = New-WorkloadPortables 'morrowind_snapshot' $openGlConfig $vulkanConfig
    $rows = @()
    $matrix = @(
        @('baseline-opengl', 'fixed_baseline', 'OPENGL', 'none', 'fixed_baseline-opengl'),
        @('candidate-opengl', 'candidate', 'OPENGL', 'none', 'candidate-opengl'),
        @('previous-opengl', 'previous_main', 'OPENGL', 'none', 'previous_main-opengl'),
        @('baseline-vulkan-b1', 'fixed_baseline', 'VULKAN', 'none', 'fixed_baseline-vulkan'),
        @('candidate-vulkan-off-cold-r1', 'candidate', 'VULKAN', 'cold', 'candidate-vulkan', 'Off', 'baseline-candidate'),
        @('candidate-vulkan-off-warm-r1', 'candidate', 'VULKAN', 'warm', 'candidate-vulkan', 'Off', 'candidate-baseline'),
        @('previous-vulkan-b1', 'previous_main', 'VULKAN', 'none', 'previous_main-vulkan'),
        @('candidate-vulkan-off-cold-r2', 'candidate', 'VULKAN', 'cold', 'candidate-vulkan-r2', 'Off', 'baseline-candidate'),
        @('candidate-vulkan-on-cold-r1', 'candidate', 'VULKAN', 'cold', 'candidate-vulkan-on', 'On', 'candidate-baseline'),
        @('candidate-vulkan-on-warm-r1', 'candidate', 'VULKAN', 'warm', 'candidate-vulkan-on', 'On', 'baseline-candidate'),
        @('candidate-vulkan-on-cold-r2', 'candidate', 'VULKAN', 'cold', 'candidate-vulkan-on-r2', 'On', 'candidate-baseline'),
        @('baseline-vulkan-b2', 'fixed_baseline', 'VULKAN', 'none', 'fixed_baseline-vulkan'),
        @('previous-vulkan-b2', 'previous_main', 'VULKAN', 'none', 'previous_main-vulkan')
    )
    for ($index = 0; $index -lt $matrix.Count; $index++) {
        $entry = $matrix[$index]
        $label = '{0:D2}-morrowind-snapshot-{1}' -f ($OrdinalBase + $index), $entry[0]
        $rows += Invoke-MorrowindCell $label $Campaign.Builds[$entry[1]] `
            $p[$entry[4]] `
            $entry[2] $entry[3] `
            $(if ($entry.Count -gt 5) { $entry[5] } else { 'Off' }) `
            $(if ($entry.Count -gt 6) { $entry[6] } else { 'baseline-candidate' })
    }
    $rows
}

$receipt = [ordered]@{
    schema_version = 2
    status = 'running'
    campaign_id = $Campaign.CampaignId
    gpu_policy = $Campaign.Host.GpuPolicy
    expected_auto_adapter_vendor = $Campaign.Host.ExpectedAutoAdapterVendor
    cells = @()
    error = $null
    final_cleanup = $null
    started_utc = [DateTimeOffset]::UtcNow.ToString('o')
}

try {
    if (Test-Path -LiteralPath $root) {
        throw "Refusing to overwrite retail evidence: $root"
    }
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    Assert-HostIdle $Campaign 'retail campaign start'
    Assert-AutoGpuConfig $Campaign.Retail.Pgr2OpenGlConfig
    Assert-AutoGpuConfig $Campaign.Retail.Pgr2VulkanConfig
    $receipt.cells += Invoke-Pgr2Workload 'pgr2_snapshot' 'Snapshot' 1
    $receipt.cells += Invoke-Pgr2Workload 'pgr2_full_start' 'FreshBoot' 13
    $receipt.cells += Invoke-MorrowindWorkload 25
    $receipt.status = 'passed'
} catch {
    $receipt.status = 'failed'
    $receipt.error = $_.Exception.Message
} finally {
    $receipt.final_cleanup = Invoke-CampaignCleanup $Campaign 'retail final'
    if ($receipt.final_cleanup.status -ne 'passed') {
        $receipt.status = 'failed'
        $extra = $receipt.final_cleanup.errors -join '; '
        $receipt.error = if ($receipt.error) { "$($receipt.error); $extra" } else { $extra }
    }
    $receipt.completed_utc = [DateTimeOffset]::UtcNow.ToString('o')
    Write-JsonAtomic (Join-Path $root 'campaign.json') $receipt
}

$receipt | ConvertTo-Json -Depth 20 -Compress
if ($receipt.status -ne 'passed') { throw $receipt.error }
