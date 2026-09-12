$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Campaign = & (Join-Path $PSScriptRoot 'campaign-config.ps1')
. (Join-Path $PSScriptRoot 'campaign-common.ps1')

$retailPath = Join-Path $Campaign.ResultsRoot 'retail\campaign.json'
$xisoPath = Join-Path $Campaign.ResultsRoot 'full-xiso\campaign.json'
$outputRoot = Join-Path $Campaign.ResultsRoot 'tables'
New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null

$retail = Get-Content -LiteralPath $retailPath -Raw | ConvertFrom-Json -AsHashtable
$xiso = Get-Content -LiteralPath $xisoPath -Raw | ConvertFrom-Json -AsHashtable
if ($retail.status -ne 'passed' -or $xiso.status -ne 'passed') {
    throw 'Tables require completed XISO and retail campaigns.'
}

function Get-Median([object[]]$Values) {
    $numbers = @($Values | Where-Object { $null -ne $_ } |
        ForEach-Object { [double]$_ } | Sort-Object)
    if (-not $numbers.Count) { return $null }
    $middle = [math]::Floor($numbers.Count / 2)
    if ($numbers.Count % 2) { return [double]$numbers[$middle] }
    ([double]$numbers[$middle - 1] + [double]$numbers[$middle]) / 2.0
}

function Format-Number([object]$Value) {
    if ($null -eq $Value) { return 'n/a' }
    '{0:0.000}' -f [double]$Value
}

function Write-MarkdownTable(
    [string]$Path,
    [string]$Title,
    [string[]]$Headers,
    [object[]]$Rows
) {
    $lines = @("# $Title", '', ('| ' + ($Headers -join ' | ') + ' |'))
    $lines += '| ' + (@($Headers | ForEach-Object { '---' }) -join ' | ') + ' |'
    foreach ($row in $Rows) {
        $values = @($Headers | ForEach-Object {
            ([string]$row.$_).Replace('|', '\|').Replace("`r", ' ').Replace("`n", ' ')
        })
        $lines += '| ' + ($values -join ' | ') + ' |'
    }
    $lines | Set-Content -LiteralPath $Path -Encoding utf8
}

$cellRows = @($retail.cells | ForEach-Object {
    [pscustomobject][ordered]@{
        Workload = $_.workload
        Renderer = $_.renderer
        Role = $_.role
        Hybrid = $_.hybrid_ubershaders
        Cache = $_.cache_phase
        Run = $_.label
        FPS = Format-Number $_.metrics.fps
        Average_ms = Format-Number $_.metrics.frame_average_ms
        P95_ms = Format-Number $_.metrics.p95_ms
        P99_ms = Format-Number $_.metrics.p99_ms
        Maximum_ms = Format-Number $_.metrics.max_ms
        Stalls = $_.metrics.stalls
        Frames = $_.metrics.guest_frames
        Status = $_.status
    }
})
$cellRows | Export-Csv -LiteralPath (Join-Path $outputRoot 'retail-cells.csv') `
    -NoTypeInformation -Encoding utf8
Write-MarkdownTable (Join-Path $outputRoot 'retail-cells.md') `
    'PR71 complete retail cell results' `
    @('Workload','Renderer','Role','Hybrid','Cache','Run','FPS','Average_ms','P95_ms',
      'P99_ms','Maximum_ms','Stalls','Frames','Status') $cellRows

$metricDefinitions = @(
    [ordered]@{ Key='fps'; Label='FPS / cadence'; Unit='fps'; Higher=$true },
    [ordered]@{ Key='frame_average_ms'; Label='Mean interval'; Unit='ms'; Higher=$false },
    [ordered]@{ Key='p95_ms'; Label='p95 interval'; Unit='ms'; Higher=$false },
    [ordered]@{ Key='p99_ms'; Label='p99 interval'; Unit='ms'; Higher=$false },
    [ordered]@{ Key='max_ms'; Label='Maximum interval'; Unit='ms'; Higher=$false },
    [ordered]@{ Key='stalls'; Label='Stalls >= 75 ms'; Unit='count'; Higher=$false }
)

$comparisonRows = @()
$gateRows = @()
foreach ($workload in @($retail.cells.workload | Sort-Object -Unique)) {
    foreach ($renderer in @($retail.cells |
        Where-Object workload -EQ $workload | ForEach-Object renderer |
        Sort-Object -Unique)) {
        $scope = @($retail.cells | Where-Object {
            $_.workload -eq $workload -and $_.renderer -eq $renderer
        })
        $baseline = @($scope | Where-Object role -EQ 'fixed_baseline')
        $previous = @($scope | Where-Object role -EQ 'previous_main')
        $candidateKeys = @($scope | Where-Object role -EQ 'candidate' |
            ForEach-Object { "$($_.hybrid_ubershaders)/$($_.cache_phase)" } |
            Sort-Object -Unique)
        foreach ($candidateKey in $candidateKeys) {
            $parts = $candidateKey.Split('/', 2)
            $hybrid = $parts[0]
            $phase = $parts[1]
            $candidate = @($scope | Where-Object {
                $_.role -eq 'candidate' -and $_.cache_phase -eq $phase -and
                $_.hybrid_ubershaders -eq $hybrid
            })
            foreach ($metric in $metricDefinitions) {
                $baseValue = Get-Median @($baseline | ForEach-Object { $_.metrics[$metric.Key] })
                $prevValue = Get-Median @($previous | ForEach-Object { $_.metrics[$metric.Key] })
                $candValue = Get-Median @($candidate | ForEach-Object { $_.metrics[$metric.Key] })
                $baseImprovement = if ($null -ne $baseValue -and $null -ne $candValue) {
                    Get-ImprovementPercent $baseValue $candValue $metric.Higher
                } else { $null }
                $prevImprovement = if ($null -ne $prevValue -and $null -ne $candValue) {
                    Get-ImprovementPercent $prevValue $candValue $metric.Higher
                } else { $null }
                $previousVsBaseline = if ($null -ne $baseValue -and $null -ne $prevValue) {
                    Get-ImprovementPercent $baseValue $prevValue $metric.Higher
                } else { $null }
                $comparisonRows += [pscustomobject][ordered]@{
                    Workload = $workload
                    Renderer = $renderer
                    Candidate_cache = $phase
                    Candidate_hybrid = $hybrid
                    Metric = $metric.Label
                    Unit = $metric.Unit
                    Baseline_median = Format-Number $baseValue
                    Previous_main_median = Format-Number $prevValue
                    Candidate_median = Format-Number $candValue
                    Improvement_vs_baseline = Format-Improvement $baseImprovement
                    Improvement_vs_previous_main = Format-Improvement $prevImprovement
                    Previous_main_vs_baseline = Format-Improvement $previousVsBaseline
                    Baseline_runs = $baseline.Count
                    Previous_runs = $previous.Count
                    Candidate_runs = $candidate.Count
                }
                if ($renderer -eq 'vulkan' -and
                    $metric.Key -in @('frame_average_ms', 'p95_ms', 'p99_ms', 'max_ms')) {
                    $gateRows += [pscustomobject][ordered]@{
                        Workload = $workload
                        Renderer = $renderer
                        Candidate_cache = $phase
                        Candidate_hybrid = $hybrid
                        Metric = $metric.Label
                        Improvement_vs_baseline = $baseImprovement
                        Improvement_vs_previous_main = $prevImprovement
                        Incremental_gate = if ($candidate.Count -lt 2 -or
                            $baseline.Count -lt 2 -or $previous.Count -lt 2 -or
                            $null -eq $baseImprovement -or $null -eq $prevImprovement) {
                            'INCOMPLETE'
                        } elseif ($prevImprovement -lt -2.0) {
                            'HOLD'
                        } else { 'PASS' }
                        Cycle_gate = if ($candidate.Count -lt 2 -or
                            $baseline.Count -lt 2 -or $previous.Count -lt 2 -or
                            $null -eq $baseImprovement -or $null -eq $prevImprovement) {
                            'INCOMPLETE'
                        } elseif ($baseImprovement -lt -2.0) {
                            'HOLD'
                        } else { 'PASS' }
                    }
                }
            }
        }
    }
}
$comparisonRows | Export-Csv -LiteralPath (Join-Path $outputRoot 'improvement-comparisons.csv') `
    -NoTypeInformation -Encoding utf8
Write-MarkdownTable (Join-Path $outputRoot 'improvement-comparisons.md') `
    'PR71 Improvement comparisons (+ favorable, - adverse)' `
    @('Workload','Renderer','Candidate_cache','Candidate_hybrid','Metric','Unit','Baseline_median',
      'Previous_main_median','Candidate_median','Improvement_vs_baseline',
      'Improvement_vs_previous_main','Previous_main_vs_baseline','Baseline_runs',
      'Previous_runs','Candidate_runs') `
    $comparisonRows

$cacheRows = @($retail.cells | Where-Object {
    $_.role -eq 'candidate' -and $_.renderer -eq 'vulkan'
} | ForEach-Object {
    [pscustomobject][ordered]@{
        Workload = $_.workload
        Run = $_.label
        Cache = $_.cache_phase
        File = if ($_.cache_after) { $_.cache_after.name } else { 'missing' }
        Before_SHA256 = if ($_.cache_before) { $_.cache_before.sha256 } else { 'none' }
        After_SHA256 = if ($_.cache_after) { $_.cache_after.sha256 } else { 'none' }
        Hits = if ($_.cache_stats) { $_.cache_stats.hits } else { 'missing' }
        Misses = if ($_.cache_stats) { $_.cache_stats.misses } else { 'missing' }
        Rejections = if ($_.cache_stats) { $_.cache_stats.rejections } else { 'missing' }
        Fallbacks = if ($_.cache_stats) { $_.cache_stats.fallbacks } else { 'missing' }
        Write = if ($_.cache_stats) { $_.cache_stats.write } else { 'missing' }
    }
})
$cacheRows | Export-Csv -LiteralPath (Join-Path $outputRoot 'cache-proof.csv') `
    -NoTypeInformation -Encoding utf8
Write-MarkdownTable (Join-Path $outputRoot 'cache-proof.md') `
    'PR71 cache proof' `
    @('Workload','Run','Cache','File','Before_SHA256','After_SHA256','Hits',
      'Misses','Rejections','Fallbacks','Write') $cacheRows

$xisoRows = @($xiso.cells | ForEach-Object {
    $gated = $_.workload -eq 'full_xiso_gated_leaf'
    [pscustomobject][ordered]@{
        Role = $_.role
        Renderer = $_.renderer
        Hybrid = if ($gated) { 'off' } else { $_.hybrid_ubershaders }
        Cache = if ($gated) { 'isolated' } else { $_.cache_phase }
        Records = if ($gated) {
            if ($_.classification -eq 'completed') { 1 } else { 0 }
        } else { $_.record_count }
        Non_PASS = if ($gated) {
            if ($_.outcome -eq 'PASS') { '' } else { "$($_.test_id):$($_.outcome)" }
        } else { $_.non_pass_records -join ', ' }
        Functional_hash = if ($gated) { 'isolated control' } else {
            $_.functional_hash_validation
        }
        Validation = if ($gated) {
            if ($_.renderer -eq 'vulkan') { 'recorded per-cell' } else { 'n/a' }
        } elseif ($_.renderer -eq 'vulkan') {
            if ($_.validation_active -and $_.unique_vuid_count -eq 0) { 'PASS' } else { 'FAIL' }
        } else { 'n/a' }
        Cache_hits = if (-not $gated -and $_.cache_stats) { $_.cache_stats.hits } else { 'n/a' }
        Cache_misses = if (-not $gated -and $_.cache_stats) { $_.cache_stats.misses } else { 'n/a' }
        Status = if ($gated) { "$($_.classification):$($_.outcome)" } else { $_.status }
    }
})
$xisoRows | Export-Csv -LiteralPath (Join-Path $outputRoot 'full-xiso.csv') `
    -NoTypeInformation -Encoding utf8
Write-MarkdownTable (Join-Path $outputRoot 'full-xiso.md') `
    'PR71 complete maintained XISO results and isolated baseline controls' `
    @('Role','Renderer','Hybrid','Cache','Records','Non_PASS','Functional_hash','Validation',
      'Cache_hits','Cache_misses','Status') $xisoRows

$incrementalHolds = @($gateRows | Where-Object Incremental_gate -EQ 'HOLD')
$cycleHolds = @($gateRows | Where-Object Cycle_gate -EQ 'HOLD')
$incomplete = @($gateRows | Where-Object {
    $_.Incremental_gate -eq 'INCOMPLETE' -or $_.Cycle_gate -eq 'INCOMPLETE'
})
$warmProof = @($retail.cells | Where-Object {
    $_.role -eq 'candidate' -and $_.renderer -eq 'vulkan' -and
    $_.cache_phase -eq 'warm'
})
# A warm run may discover additional shaders because guest execution is not
# instruction-identical.  Hits plus loaded bytes prove cross-run reuse; all
# new misses remain reported and must be republished without fallback.
$cachePass = $warmProof.Count -ge 8 -and @($warmProof | Where-Object {
    -not $_.cache_stats -or $_.cache_stats.hits -le 0 -or
    $_.cache_stats.rejections -ne 0 -or $_.cache_stats.fallbacks -ne 0 -or
    $_.cache_stats.loaded_bytes -le 0 -or $_.cache_stats.write -ne 'published' -or
    -not $_.cache_before -or -not $_.cache_after
}).Count -eq 0

$summary = [ordered]@{
    schema_version = 2
    campaign_id = $Campaign.CampaignId
    status = if ($incrementalHolds.Count -eq 0 -and $cycleHolds.Count -eq 0 -and
        $incomplete.Count -eq 0 -and $cachePass) {
        'PASS'
    } else { 'HOLD' }
    interpretation = 'Improvement is positive when favorable and negative when adverse.'
    reporting = [ordered]@{ tables_only = $true; graphs = $false }
    shader_controls = $Campaign.Controls
    fixed_baseline = $Campaign.Builds.fixed_baseline
    previous_main = $Campaign.Builds.previous_main
    candidate = $Campaign.Builds.candidate
    xiso_status = $xiso.status
    retail_status = $retail.status
    warm_cache_proof = if ($cachePass) { 'PASS' } else { 'FAIL' }
    incremental_patch_gate = if ($incrementalHolds.Count -eq 0 -and
        $incomplete.Count -eq 0 -and $cachePass) { 'PASS' } else { 'HOLD' }
    cycle_baseline_gate = if ($cycleHolds.Count -eq 0 -and
        $incomplete.Count -eq 0) { 'PASS' } else { 'HOLD' }
    incremental_performance_holds = $incrementalHolds
    cycle_baseline_holds = $cycleHolds
    performance_gate_incomplete = $incomplete
    tables = [ordered]@{
        retail_cells = 'tables/retail-cells.md'
        improvement_comparisons = 'tables/improvement-comparisons.md'
        cache_proof = 'tables/cache-proof.md'
        full_xiso = 'tables/full-xiso.md'
    }
    generated_utc = [DateTimeOffset]::UtcNow.ToString('o')
}
Write-JsonAtomic (Join-Path $Campaign.ResultsRoot 'qualification-summary.json') $summary
$summary | ConvertTo-Json -Depth 20 -Compress
# HOLD is a review decision, not a campaign infrastructure failure.  The
# controller records successful table generation and reads this JSON before
# recommending merge.
