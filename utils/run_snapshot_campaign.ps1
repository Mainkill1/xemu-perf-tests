param(
 [Parameter(Mandatory=$true)][string]$ManifestPath,
 [ValidateSet('pilot','measured')][string]$Phase,
 [int]$StartIndex=1,
 [int]$EndIndex=100
)
$ErrorActionPreference='Stop'
$m=Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
if([Diagnostics.Process]::GetCurrentProcess().SessionId -ne 1){throw 'Interactive Session 1 is required'}
New-Item -ItemType Directory -Path $m.receipt_root -Force | Out-Null
function Assert-Idle {
 $active=@(Get-Process -Name xemu,PresentMon,wpr,wpa,xperf -ErrorAction SilentlyContinue)
 if($active.Count){throw 'Automatic admission found an emulator or capture/analysis process; no process was terminated'}
}
Assert-Idle
$verified=@()
foreach($inputFile in $m.inputs){
 $actual=(Get-FileHash -LiteralPath $inputFile.path -Algorithm SHA256).Hash.ToLowerInvariant()
 if($actual -ne $inputFile.sha256){throw "Pinned input mismatch: $($inputFile.path)"}
 $verified += [ordered]@{path=$inputFile.path;sha256=$actual}
}
foreach($case in @($m.cases | Where-Object {$_.phase -eq $Phase -and $_.index -ge $StartIndex -and $_.index -le $EndIndex})){
 $build=$m.builds.($case.build)
 $receiptPath=Join-Path $m.receipt_root ($case.run_id+'.receipt.json')
 if(Test-Path -LiteralPath $receiptPath){throw "Refusing to overwrite receipt: $($case.run_id)"}
 if(Test-Path -LiteralPath (Join-Path $m.capture_root $case.run_id)){throw "Refusing to reuse capture directory: $($case.run_id)"}
 $receipt=[ordered]@{schema_version=1;campaign=$m.campaign;case=$case;source_commit=$build.source;source_tree=$build.tree;exe_sha256=$build.sha256;status='running';started_utc=[DateTime]::UtcNow.ToString('o');inputs=$verified;result=$null;error=$null;cleanup_verified=$false}
 $receipt | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $receiptPath -Encoding utf8
 try {
  Assert-Idle
  $prior=Join-Path (Split-Path -Parent $build.path) 'PGR2-RESULT.json'
  if(Test-Path -LiteralPath $prior){Copy-Item -LiteralPath $prior -Destination (Join-Path $m.receipt_root ($case.run_id+'.prior-build-result.json'))}
  if((Get-FileHash -LiteralPath $build.path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $build.sha256){throw 'Executable identity changed'}
  $result=& $m.runner -Renderer $case.renderer -DurationSeconds $case.seconds -RunId $case.run_id -Xemu $build.path -ExpectedXemuSha256 $build.sha256 -SourceCommit $build.source
  $receipt.result=$result
  $complete=Get-Content -LiteralPath (Join-Path $result.evidence 'complete.json') -Raw | ConvertFrom-Json
  $hdd=Get-Content -LiteralPath $result.hdd_lifecycle -Raw | ConvertFrom-Json
  if($complete.status -ne 'complete' -or $complete.functional_status -ne 'complete' -or $complete.measurement_status -ne 'complete'){throw 'Run-local completion gate failed'}
  if($result.xemu_sha256 -ne $build.sha256 -or $result.renderer -ne $case.renderer){throw 'Returned identity mismatch'}
  if($result.focus_loss_samples -ne 0 -or $result.etw_lost_events -ne 0 -or $result.etw_lost_buffers -ne 0){throw 'Focus or ETW loss gate failed'}
  if($result.guest_frame_count -le 0 -or $result.presentmon_frame_count -le 0){throw 'Missing guest or host samples'}
  if($hdd.cleanup_status -ne 'complete' -or $hdd.seed_sha256_final -ne $m.seed_sha256){throw 'HDD cleanup or seed-integrity gate failed'}
  Assert-Idle
  $receipt.cleanup_verified=$true
  $receipt.status='CAPTURE_COMPLETE'
 } catch {
  $receipt.status='INVALID'
  $receipt.error=$_.Exception.Message
 } finally {
  $receipt.completed_utc=[DateTime]::UtcNow.ToString('o')
  $receipt | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $receiptPath -Encoding utf8
 }
 [ordered]@{run_id=$case.run_id;status=$receipt.status;error=$receipt.error} | ConvertTo-Json -Compress
 if($receipt.status -ne 'CAPTURE_COMPLETE'){throw "Campaign stopped at $($case.run_id); preserve and inspect the receipt"}
}
