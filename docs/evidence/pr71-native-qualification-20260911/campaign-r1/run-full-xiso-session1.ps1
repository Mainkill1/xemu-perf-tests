$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Campaign = & (Join-Path $PSScriptRoot 'campaign-config.ps1')
. (Join-Path $PSScriptRoot 'campaign-common.ps1')

Assert-NoPlaceholders $Campaign 'PR71 campaign'
$buildReceipts = @()
foreach ($role in @('fixed_baseline', 'previous_main', 'candidate')) {
    $buildReceipts += Assert-BuildContract $Campaign.Builds[$role]
}
$root = Join-Path $Campaign.ResultsRoot 'full-xiso'
$receiptPath = Join-Path $root 'campaign.json'
$privateHdd = 'C:\xemu-lab\suite\work\test.img'
$oracleLedger = Join-Path $root 'functional-hash-ledger.json'
$gatedTests = @(
    [ordered]@{ stable = 'pfifo_packet_boundary.array_element16_overflow'; legacy = 'PFIFOPacketBoundary::pfifo.boundary-array-element16' },
    [ordered]@{ stable = 'pfifo_packet_boundary.array_element32_overflow'; legacy = 'PFIFOPacketBoundary::pfifo.boundary-array-element32' },
    [ordered]@{ stable = 'pfifo_packet_boundary.inline_array_overflow'; legacy = 'PFIFOPacketBoundary::pfifo.boundary-inline-array' },
    [ordered]@{ stable = 'pfifo_packet_boundary.incrementing_inline_fallback'; legacy = 'PFIFOPacketBoundary::pfifo.incrementing-inline-fallback' },
    [ordered]@{ stable = 'texture_cubemap_fallback.unbordered_subblock_dxt1'; legacy = 'TextureCubemapFallback::UnborderedSubblockDxt1' }
)

function Assert-Sequence([string]$Label, [object[]]$Actual, [object[]]$Expected) {
    $a = @($Actual | Sort-Object)
    $e = @($Expected | Sort-Object)
    if ($a.Count -ne $e.Count -or ($a -join ',') -ne ($e -join ',')) {
        throw "$Label mismatch: expected $($e -join ','), observed $($a -join ',')"
    }
}

function Invoke-XisoCell(
    [string]$Label,
    [System.Collections.IDictionary]$Build,
    [System.Collections.IDictionary]$Portable,
    [ValidateSet('opengl', 'vulkan')][string]$Backend,
    [ValidateSet('none', 'cold', 'warm')][string]$CachePhase,
    [bool]$IncludeGated,
    [ValidateSet('off', 'on')][string]$HybridUbershaders = 'off',
    [ValidateSet('baseline-candidate', 'candidate-baseline')][string]$RunOrder = 'baseline-candidate'
) {
    Assert-HostIdle $Campaign "before $Label"
    $validation = $Backend -eq 'vulkan'
    $cacheBefore = Get-SpirvCacheReceipt $Portable.directory
    if ($Backend -eq 'opengl' -and $cacheBefore) {
        throw "$Label unexpectedly started with a Vulkan cache"
    }
    if ($CachePhase -eq 'cold' -and $cacheBefore) {
        throw "$Label was not cold"
    }
    if ($CachePhase -eq 'warm' -and -not $cacheBefore) {
        throw "$Label has no cold cache seed"
    }

    $outputPath = Join-Path $root "$Label-runner-output.txt"
    $experimentRole = if ($Build.Role -eq 'candidate') { 'candidate' } else { 'baseline' }
    $expectedRecordCount = if ($IncludeGated) {
        $Campaign.Xiso.RecordCount
    } else { $Campaign.Xiso.RegisteredRecordCount }
    $expectedLeafCount = if ($IncludeGated) {
        $Campaign.Xiso.LeafCount
    } else { $Campaign.Xiso.RegisteredLeafCount }
    $arguments = @(
        $Campaign.Xiso.Runner,
        '--mode', 'perf',
        '--xemu', $Portable.xemu,
        '--guest-iso', $Campaign.Xiso.Image,
        '--catalog', $Campaign.Xiso.Catalog,
        '--guest-source-commit', $Campaign.Xiso.TestSourceCommit,
        '--guest-source-tree', $Campaign.Xiso.TestSourceTree,
        '--backend', $Backend,
        '--scale', '1',
        '--memory-megabytes', '64',
        '--warmup-iterations', '0',
        '--measurement-iterations-multiplier', '1',
        '--completion-mode', 'per_iteration',
        '--timeout-seconds', '1800',
        '--host-telemetry', 'off',
        '--comparison-role', $Build.Role,
        '--comparison-baseline-commit', '9f618d6d8c4c446ef023955f3d4de22f661f61a4',
        '--comparison-previous-main-commit', '5edff26383c6440da35bc92b9fca35f4a404b03b',
        '--run-order', $RunOrder,
        '--shader-cache', 'on',
        '--hybrid-ubershaders', $HybridUbershaders,
        '--experiment-role', $experimentRole,
        '--allow-missing-live-markers',
        '--oracle-ledger', $oracleLedger,
        '--full-suite',
        '--expected-record-count', [string]$expectedRecordCount
    )
    if ($IncludeGated) { $arguments += '--enable-xemu-only-tests' }
    if ($validation) { $arguments += '--vulkan-validation' }

    $cell = $null
    $failure = $null
    $cleanup = $null
    try {
        $output = @(& $Campaign.Xiso.Python @arguments 2>&1 |
            Tee-Object -FilePath $outputPath)
        $exitCode = $LASTEXITCODE
        # The maintained image has intentional inherited non-PASS records.
        if ($exitCode -ne 1) {
            throw "$Label runner exit was $exitCode; expected 1 for the pinned oracle set"
        }
        $evidenceLine = @($output | ForEach-Object { [string]$_ } |
            Where-Object { $_ -like 'Evidence: *' }) | Select-Object -First 1
        if (-not $evidenceLine) { throw "$Label reported no evidence directory" }
        $evidence = $evidenceLine.Substring('Evidence: '.Length).Trim()
        $summary = Get-Content -LiteralPath (Join-Path $evidence 'summary.json') `
            -Raw | ConvertFrom-Json -AsHashtable
        $guestConfig = Get-Content -LiteralPath (Join-Path $evidence 'guest-config.json') `
            -Raw | ConvertFrom-Json -AsHashtable

        if ($summary.status -ne 'FAILED' -or $summary.backend -ne $Backend -or
            $summary.guest_image.sha256 -ne $Campaign.Xiso.ImageSha256 -or
            $summary.guest_image.source_commit -ne $Campaign.Xiso.TestSourceCommit -or
            $summary.guest_image.source_tree -ne $Campaign.Xiso.TestSourceTree -or
            $summary.record_count_validation.catalog_sha256 -ne $Campaign.Xiso.CatalogSha256 -or
            $summary.record_count_validation.catalog_id -ne $Campaign.Xiso.CatalogId) {
            throw "$Label summary identity mismatch"
        }
        if ($summary.build.SOURCE_SHA -ne $Build.SourceCommit -or
            $summary.build.SOURCE_TREE -ne $Build.Tree -or
            $summary.build.XEMU_SHA256 -ne $Build.XemuSha256) {
            throw "$Label exact build identity mismatch"
        }
        if (-not $summary.host_process.launch.validated -or
            $summary.host_process.launch.actual_sha256 -ne $Build.XemuSha256) {
            throw "$Label launched-process identity was not validated"
        }
        if ($summary.record_count_validation.status -ne 'PASSED' -or
            $summary.record_count_validation.expected -ne $expectedRecordCount -or
            $summary.record_count_validation.actual -ne $expectedRecordCount -or
            $summary.record_count_validation.expected_leaf_count -ne $expectedLeafCount -or
            $summary.record_count_validation.actual_leaf_count -ne $expectedLeafCount -or
            $summary.record_count_validation.expected_group_count -ne $Campaign.Xiso.GroupCount -or
            $summary.record_count_validation.actual_group_count -ne $Campaign.Xiso.GroupCount -or
            @($summary.records).Count -ne $expectedRecordCount) {
            throw "$Label record contract failed"
        }
        $expectedNonPass = if ($Backend -eq 'opengl') {
            if ($IncludeGated) { $Campaign.Xiso.ExpectedOpenGlNonPass } else {
                @($Campaign.Xiso.ExpectedOpenGlNonPass | Where-Object {
                    $_ -ne 'texture_cubemap_fallback.unbordered_subblock_dxt1'
                })
            }
        } else {
            $Campaign.Xiso.ExpectedVulkanNonPass
        }
        $observedNonPass = @($summary.records | Where-Object outcome -NE 'PASS' |
            ForEach-Object id)
        Assert-Sequence "$Label non-PASS records" $observedNonPass $expectedNonPass
        if ($summary.functional_hash_validation.status -ne 'PASSED') {
            throw "$Label functional hash validation failed"
        }
        if ([bool]$guestConfig.settings.enable_xemu_only_tests -ne $IncludeGated -or
            $guestConfig.settings.skip_tests_by_default) {
            throw "$Label did not run its exact full-suite scope"
        }
        if ($validation -and
            (-not $summary.vulkan_validation.enabled -or
             -not $summary.vulkan_validation.active -or
             [int]$summary.vulkan_validation.unique_vuid_count -ne 0)) {
            throw "$Label Vulkan validation failed"
        }

        $cacheAfter = Get-SpirvCacheReceipt $Portable.directory
        $adapterEvidence = Get-AdapterEvidence $Backend `
            (Join-Path $evidence 'xemu.log') $Campaign.Host.ExpectedAutoAdapterVendor
        $stats = if ($Build.Role -eq 'candidate' -and $Backend -eq 'vulkan') {
            Get-SpirvStats (Join-Path $evidence 'xemu.log')
        } else { $null }
        Assert-CachePhase $CachePhase $cacheBefore $cacheAfter $stats

        $cell = [ordered]@{
            label = $Label
            workload = if ($IncludeGated) {
                'full_xiso_all_157_records'
            } else { 'full_xiso_registered_152_records' }
            role = $Build.Role
            logical_commit = $Build.LogicalCommit
            source_commit = $Build.SourceCommit
            tree = $Build.Tree
            xemu_sha256 = $Build.XemuSha256
            build_info_sha256 = Get-Sha256 $Portable.BuildInfo
            config_hashes = $summary.configuration
            renderer = $Backend
            gpu_policy = $Campaign.Host.GpuPolicy
            expected_auto_adapter_vendor = $Campaign.Host.ExpectedAutoAdapterVendor
            adapter_evidence = $adapterEvidence
            cache_phase = $CachePhase
            shader_cache = 'on'
            hybrid_ubershaders = $HybridUbershaders
            run_order = $RunOrder
            cache_before = $cacheBefore
            cache_after = $cacheAfter
            cache_stats = $stats
            evidence = $evidence
            record_count = @($summary.records).Count
            non_pass_records = $observedNonPass
            functional_hash_validation = $summary.functional_hash_validation.status
            validation_active = if ($validation) { $summary.vulkan_validation.active } else { $false }
            unique_vuid_count = if ($validation) {
                $summary.vulkan_validation.unique_vuid_count
            } else { 0 }
            status = 'passed'
            cleanup = $null
        }
    } catch {
        $failure = $_.Exception
    } finally {
        $cleanup = Invoke-CampaignCleanup $Campaign $Label @($privateHdd)
    }
    if ($cleanup.status -ne 'passed') {
        $message = $cleanup.errors -join '; '
        if ($failure) { throw "$($failure.Message); cleanup failed: $message" }
        throw "$Label cleanup failed: $message"
    }
    if ($failure) { throw $failure }
    $cell.cleanup = $cleanup
    Write-JsonAtomic (Join-Path $root "$Label.json") $cell
    [pscustomobject]$cell
}

function Invoke-GatedXisoCell(
    [string]$Label,
    [System.Collections.IDictionary]$Build,
    [ValidateSet('opengl', 'vulkan')][string]$Backend,
    [System.Collections.IDictionary]$Test
) {
    Assert-HostIdle $Campaign "before $Label"
    $validation = $Backend -eq 'vulkan'
    $portable = New-PortableBuild $Campaign $Build "xiso-$Label"
    $outputPath = Join-Path $root "$Label-runner-output.txt"
    $experimentRole = if ($Build.Role -eq 'candidate') { 'candidate' } else { 'baseline' }
    $arguments = @(
        $Campaign.Xiso.Runner,
        '--mode', 'perf',
        '--xemu', $portable.xemu,
        '--guest-iso', $Campaign.Xiso.Image,
        '--catalog', $Campaign.Xiso.Catalog,
        '--guest-source-commit', $Campaign.Xiso.TestSourceCommit,
        '--guest-source-tree', $Campaign.Xiso.TestSourceTree,
        '--backend', $Backend,
        '--scale', '1',
        '--memory-megabytes', '64',
        '--warmup-iterations', '0',
        '--measurement-iterations-multiplier', '1',
        '--completion-mode', 'per_iteration',
        '--timeout-seconds', '900',
        '--host-telemetry', 'off',
        '--comparison-role', $Build.Role,
        '--comparison-baseline-commit', '9f618d6d8c4c446ef023955f3d4de22f661f61a4',
        '--comparison-previous-main-commit', '5edff26383c6440da35bc92b9fca35f4a404b03b',
        '--run-order', 'baseline-candidate',
        '--shader-cache', 'on',
        '--hybrid-ubershaders', 'off',
        '--experiment-role', $experimentRole,
        '--allow-missing-live-markers',
        '--oracle-ledger', $oracleLedger,
        '--enable-xemu-only-tests',
        '--test-id', $Test.legacy,
        '--expected-record-count', '1'
    )
    if ($validation) { $arguments += '--vulkan-validation' }

    $cell = $null
    $failure = $null
    $cleanup = $null
    try {
        $output = @(& $Campaign.Xiso.Python @arguments 2>&1 |
            Tee-Object -FilePath $outputPath)
        $exitCode = $LASTEXITCODE
        $lines = @($output | ForEach-Object { [string]$_ })
        $evidenceLine = @($lines | Where-Object { $_ -like 'Evidence: *' }) |
            Select-Object -First 1
        if (-not $evidenceLine) { throw "$Label reported no evidence directory" }
        $evidence = $evidenceLine.Substring('Evidence: '.Length).Trim()
        $summaryPath = Join-Path $evidence 'summary.json'
        $summary = if (Test-Path -LiteralPath $summaryPath) {
            Get-Content -LiteralPath $summaryPath -Raw | ConvertFrom-Json -AsHashtable
        } else { $null }
        $logPath = Join-Path $evidence 'xemu.log'
        $logText = if (Test-Path -LiteralPath $logPath) {
            Get-Content -LiteralPath $logPath -Raw
        } else { '' }
        $combinedText = ($lines -join "`n") + "`n" + $logText

        $isInheritedAssert = (
            $combinedText -match 'Assertion failed:' -and
            $combinedText -match '(pgraph_inline_packet_fits|inline_(elements|array)_length|NV2A_MAX_BATCH_LENGTH)'
        )
        if ($isInheritedAssert) {
            $classification = 'inherited_pfifo_assert'
            $outcome = 'ABORT'
            $adapterEvidence = if (Test-Path -LiteralPath $logPath) {
                Get-AdapterEvidence $Backend $logPath $Campaign.Host.ExpectedAutoAdapterVendor
            } else { $null }
        } elseif ($exitCode -in @(0, 1)) {
            if (-not $summary) { throw "$Label completed without summary.json" }
            if ($summary.backend -ne $Backend -or
                $summary.guest_image.sha256 -ne $Campaign.Xiso.ImageSha256 -or
                $summary.record_count_validation.catalog_sha256 -ne $Campaign.Xiso.CatalogSha256 -or
                $summary.record_count_validation.catalog_id -ne $Campaign.Xiso.CatalogId -or
                $summary.record_count_validation.status -ne 'PASSED' -or
                $summary.record_count_validation.actual -ne 1 -or
                @($summary.records).Count -ne 1 -or
                $summary.records[0].id -ne $Test.stable) {
                throw "$Label completed record contract failed"
            }
            if ($summary.build.SOURCE_SHA -ne $Build.SourceCommit -or
                $summary.build.SOURCE_TREE -ne $Build.Tree -or
                $summary.build.XEMU_SHA256 -ne $Build.XemuSha256 -or
                -not $summary.host_process.launch.validated -or
                $summary.host_process.launch.actual_sha256 -ne $Build.XemuSha256) {
                throw "$Label exact build identity mismatch"
            }
            if ($validation -and
                (-not $summary.vulkan_validation.enabled -or
                 -not $summary.vulkan_validation.active -or
                 [int]$summary.vulkan_validation.unique_vuid_count -ne 0)) {
                throw "$Label Vulkan validation failed"
            }
            $classification = 'completed'
            $outcome = $summary.records[0].outcome
            $adapterEvidence = Get-AdapterEvidence $Backend $logPath `
                $Campaign.Host.ExpectedAutoAdapterVendor
        } else {
            throw "$Label exited $exitCode without the inherited PFIFO assertion signature"
        }
        $cell = [ordered]@{
            label = $Label
            workload = 'full_xiso_gated_leaf'
            test_id = $Test.stable
            legacy_test_id = $Test.legacy
            role = $Build.Role
            logical_commit = $Build.LogicalCommit
            source_commit = $Build.SourceCommit
            tree = $Build.Tree
            xemu_sha256 = $Build.XemuSha256
            renderer = $Backend
            gpu_policy = $Campaign.Host.GpuPolicy
            adapter_evidence = $adapterEvidence
            runner_exit_code = $exitCode
            classification = $classification
            outcome = $outcome
            evidence = $evidence
            status = 'recorded'
            cleanup = $null
        }
    } catch {
        $failure = $_.Exception
    } finally {
        $cleanup = Invoke-CampaignCleanup $Campaign $Label @($privateHdd)
    }
    if ($cleanup.status -ne 'passed') {
        $message = $cleanup.errors -join '; '
        if ($failure) { throw "$($failure.Message); cleanup failed: $message" }
        throw "$Label cleanup failed: $message"
    }
    if ($failure) { throw $failure }
    $cell.cleanup = $cleanup
    Write-JsonAtomic (Join-Path $root "$Label.json") $cell
    [pscustomobject]$cell
}

$receipt = [ordered]@{
    schema_version = 2
    status = 'running'
    campaign_id = $Campaign.CampaignId
    maintained_xiso = [ordered]@{
        sha256 = $Campaign.Xiso.ImageSha256
        catalog_id = $Campaign.Xiso.CatalogId
        records = $Campaign.Xiso.RecordCount
        registered_full_run_records = $Campaign.Xiso.RegisteredRecordCount
        gated_leaf_records = $gatedTests.Count
    }
    cells = @()
    error = $null
    final_cleanup = $null
    started_utc = [DateTimeOffset]::UtcNow.ToString('o')
}

try {
    if (Test-Path -LiteralPath $root) {
        if (-not (Test-Path -LiteralPath $receiptPath)) {
            throw "XISO evidence exists without a resumable receipt: $root"
        }
        $existing = Get-Content -LiteralPath $receiptPath -Raw |
            ConvertFrom-Json -AsHashtable
        if ($existing.campaign_id -ne $Campaign.CampaignId -or
            $existing.status -ne 'failed' -or @($existing.cells).Count -ne 9) {
            throw "XISO receipt is not the exact nine-cell resume point"
        }
        $receipt = $existing
        $receipt.status = 'running'
        $receipt.error = $null
        $receipt.resume_started_utc = [DateTimeOffset]::UtcNow.ToString('o')
    } else {
        New-Item -ItemType Directory -Path $root -Force | Out-Null
    }
    Assert-HostIdle $Campaign 'full XISO campaign start'
    Assert-Hash $Campaign.Xiso.Image $Campaign.Xiso.ImageSha256 'maintained XISO'
    if ((Get-Item -LiteralPath $Campaign.Xiso.Image).Length -ne $Campaign.Xiso.ImageBytes) {
        throw 'Maintained XISO size mismatch'
    }
    Assert-Hash $Campaign.Xiso.Catalog $Campaign.Xiso.CatalogSha256 'maintained catalog'

    if (@($receipt.cells).Count -eq 0) {
        $portable = [ordered]@{}
        foreach ($role in @('fixed_baseline', 'previous_main', 'candidate')) {
            $build = $Campaign.Builds[$role]
            $portable["$role-opengl"] = New-PortableBuild $Campaign $build "xiso-$role-opengl"
            $portable["$role-vulkan"] = New-PortableBuild $Campaign $build "xiso-$role-vulkan"
        }
        $portable['candidate-vulkan-on'] = New-PortableBuild $Campaign `
            $Campaign.Builds.candidate 'xiso-candidate-vulkan-on' '' 'Enabled' 'On'
        $matrix = @(
        @('01-baseline-opengl', 'fixed_baseline', 'opengl', 'none', $false, 'off', 'baseline-candidate', 'fixed_baseline-opengl'),
        @('02-candidate-opengl', 'candidate', 'opengl', 'none', $true, 'off', 'candidate-baseline', 'candidate-opengl'),
        @('03-previous-opengl', 'previous_main', 'opengl', 'none', $true, 'off', 'baseline-candidate', 'previous_main-opengl'),
        @('04-previous-vulkan', 'previous_main', 'vulkan', 'none', $true, 'off', 'candidate-baseline', 'previous_main-vulkan'),
        @('05-candidate-vulkan-off-cold', 'candidate', 'vulkan', 'cold', $true, 'off', 'baseline-candidate', 'candidate-vulkan'),
        @('06-candidate-vulkan-off-warm', 'candidate', 'vulkan', 'warm', $true, 'off', 'candidate-baseline', 'candidate-vulkan'),
        @('07-candidate-vulkan-on-cold', 'candidate', 'vulkan', 'cold', $true, 'on', 'baseline-candidate', 'candidate-vulkan-on'),
        @('08-candidate-vulkan-on-warm', 'candidate', 'vulkan', 'warm', $true, 'on', 'candidate-baseline', 'candidate-vulkan-on'),
        @('09-baseline-vulkan', 'fixed_baseline', 'vulkan', 'none', $false, 'off', 'baseline-candidate', 'fixed_baseline-vulkan')
        )
        foreach ($entry in $matrix) {
            $role = $entry[1]
            $receipt.cells += Invoke-XisoCell $entry[0] $Campaign.Builds[$role] `
                $portable[$entry[7]] $entry[2] $entry[3] $entry[4] $entry[5] $entry[6]
        }
    }
    $gatedIndex = 0
    foreach ($test in $gatedTests) {
        foreach ($backend in @('opengl', 'vulkan')) {
            $gatedIndex++
            $label = ('b{0:d2}-{1}-fixed-baseline-{2}' -f $gatedIndex,
                $test.stable.Replace('.', '-'), $backend)
            $receipt.cells += Invoke-GatedXisoCell $label `
                $Campaign.Builds.fixed_baseline $backend $test
        }
    }
    $receipt.status = 'passed'
} catch {
    $receipt.status = 'failed'
    $receipt.error = $_.Exception.Message
} finally {
    $receipt.final_cleanup = Invoke-CampaignCleanup $Campaign 'full XISO final' @($privateHdd)
    if ($receipt.final_cleanup.status -ne 'passed') {
        $receipt.status = 'failed'
        $extra = $receipt.final_cleanup.errors -join '; '
        $receipt.error = if ($receipt.error) { "$($receipt.error); $extra" } else { $extra }
    }
    $receipt.completed_utc = [DateTimeOffset]::UtcNow.ToString('o')
    Write-JsonAtomic $receiptPath $receipt
}

$receipt | ConvertTo-Json -Depth 20 -Compress
if ($receipt.status -ne 'passed') { throw $receipt.error }
