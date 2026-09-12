$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Campaign = & (Join-Path $PSScriptRoot 'campaign-config.ps1')
. (Join-Path $PSScriptRoot 'campaign-common.ps1')

Assert-NoPlaceholders $Campaign 'PR71 campaign'
if ([IO.Path]::GetFullPath($PSScriptRoot) -ne [IO.Path]::GetFullPath($Campaign.PackageRoot)) {
    throw "Package path mismatch: expected $($Campaign.PackageRoot), running $PSScriptRoot"
}
if (Test-Path -LiteralPath $Campaign.ResultsRoot) {
    throw "Refusing to overwrite an existing campaign: $($Campaign.ResultsRoot)"
}
New-Item -ItemType Directory -Path $Campaign.ResultsRoot -Force | Out-Null

$receipt = [ordered]@{
    schema_version = 2
    status = 'running'
    campaign_id = $Campaign.CampaignId
    started_utc = [DateTimeOffset]::UtcNow.ToString('o')
    host_admission = $null
    builds = @()
    script_manifest = @()
    phases = @()
    error = $null
    final_cleanup = $null
}
$receiptPath = Join-Path $Campaign.ResultsRoot 'campaign-manifest.json'

try {
    Assert-HostIdle $Campaign 'campaign start'
    # Memory and GPU inventory are admitted once for the whole campaign.
    $receipt.host_admission = Get-HostAdmission $Campaign
    foreach ($role in @('fixed_baseline', 'previous_main', 'candidate')) {
        $receipt.builds += Assert-BuildContract $Campaign.Builds[$role]
    }
    foreach ($file in @(Get-ChildItem -LiteralPath $PSScriptRoot -File |
        Sort-Object Name)) {
        $receipt.script_manifest += [ordered]@{
            name = $file.Name
            bytes = $file.Length
            sha256 = Get-Sha256 $file.FullName
        }
    }
    Write-JsonAtomic $receiptPath $receipt

    $phaseStart = [DateTimeOffset]::UtcNow
    & (Join-Path $PSScriptRoot 'run-full-xiso-session1.ps1') | Out-Null
    $receipt.phases += [ordered]@{
        name = 'full_xiso_157'
        status = 'passed'
        started_utc = $phaseStart.ToString('o')
        completed_utc = [DateTimeOffset]::UtcNow.ToString('o')
    }
    Write-JsonAtomic $receiptPath $receipt

    $phaseStart = [DateTimeOffset]::UtcNow
    & (Join-Path $PSScriptRoot 'run-retail-session1.ps1') | Out-Null
    $receipt.phases += [ordered]@{
        name = 'retail'
        status = 'passed'
        started_utc = $phaseStart.ToString('o')
        completed_utc = [DateTimeOffset]::UtcNow.ToString('o')
    }
    Write-JsonAtomic $receiptPath $receipt

    $phaseStart = [DateTimeOffset]::UtcNow
    & (Join-Path $PSScriptRoot 'write-results.ps1') | Out-Null
    $receipt.phases += [ordered]@{
        name = 'tables_and_acceptance'
        status = 'passed'
        started_utc = $phaseStart.ToString('o')
        completed_utc = [DateTimeOffset]::UtcNow.ToString('o')
    }
    $receipt.status = 'passed'
} catch {
    $receipt.status = 'failed'
    $receipt.error = $_.Exception.Message
} finally {
    $suiteRoot = Split-Path -Parent $Campaign.Xiso.Runner
    $receipt.final_cleanup = Invoke-CampaignCleanup $Campaign 'campaign final' `
        @(Join-Path $suiteRoot 'work\test.img')
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
