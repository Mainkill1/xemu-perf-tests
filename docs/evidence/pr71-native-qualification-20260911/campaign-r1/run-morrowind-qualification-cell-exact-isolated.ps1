<#
.SYNOPSIS
Runs one unattended Morrowind snapshot qualification cell.
.DESCRIPTION
Clones the fixed snapshot HDD, waits five seconds after QMP reports running,
sends Start and then B, captures the scene, measures display-write cadence,
and removes the private HDD on success or failure. Run through the Session 1 GUI
pipe. The cadence is a guest progress signal, not displayed FPS. A cleanup
failure remains explicit so the caller can quarantine the host.
.PARAMETER Root
New run directory; existing directories are rejected.
.PARAMETER Xemu
Exact executable to test.
.PARAMETER XemuSha256
Required SHA-256 of Xemu.
.PARAMETER SourceCommit
Source revision recorded in the result.
.PARAMETER Renderer
VULKAN or OPENGL.
.PARAMETER DurationSeconds
Uninterrupted measurement duration after Start/B; default 10 seconds.
.PARAMETER PresentInterval
Presentation interval for this run. Use 2 for the half-refresh candidate.
.EXAMPLE
.\run-morrowind-qualification-cell.ps1 -Root C:\xemu-lab\runs\mw-candidate-vk -Xemu C:\xemu-lab\test-builds\candidate\xemu.exe -XemuSha256 '<sha256>' -SourceCommit '<commit>' -Renderer VULKAN
#>
[CmdletBinding()]
param(
 [Parameter(Mandatory)][string]$Root,
 [Parameter(Mandatory)][ValidateSet('fixed_baseline','previous_main','candidate')][string]$Role,
 [Parameter(Mandatory)][string]$Xemu,
 [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{64}$')][string]$XemuSha256,
 [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$SourceCommit,
 [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$SourceTree,
 [Parameter(Mandatory)][ValidateSet('VULKAN','OPENGL')][string]$Renderer,
 [Parameter(Mandatory)][string]$SeedHdd,
 [Parameter(Mandatory)][string]$ConfigSource,
 [ValidateSet('Enabled','Disabled')][string]$ShaderCache='Enabled',
 [ValidateSet('Off','On')][string]$HybridUbershaders='Off',
 [Parameter(Mandatory)][string]$Disc,
 [ValidateSet(0,2)][int]$PresentInterval=0,
 [ValidateRange(10,600)][int]$DurationSeconds=10
)
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
if([Diagnostics.Process]::GetCurrentProcess().SessionId-ne 1){throw 'Use the Session 1 GUI pipe'}
$control=Join-Path $PSScriptRoot 'morrowind-control-exact-isolated.ps1'
$seed=$SeedHdd;$seedSha='d178ecc4154abad5fc7cb9e428f380a1c8d49d20cbed66ba552eaaa6ed7514ad';$snapshot='vm-20260905015459'
$resultPath=Join-Path $Root 'result.json';$private=Join-Path $Root 'private-hdd.qcow2';$result=[ordered]@{schema_version=2;status='running';role=$Role;source_commit=$SourceCommit;source_tree=$SourceTree;executable_sha256=$XemuSha256;renderer=$Renderer;present_interval=if($PresentInterval-eq 2){2}else{1};present_interval_explicit=($PresentInterval-eq 2);snapshot=$snapshot;input_sequence='confirmed QMP running; wait 5s; Start; wait 2s; B; wait 2s; uninterrupted measurement';duration_seconds=$DurationSeconds;metric='NV2A display-write increment cadence proxy; not rendered/displayed FPS';private_hdd_deleted=$false;cleanup=''}
function Hash([string]$Path){(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Save-Result{$tmp=$resultPath+'.tmp';$result|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $tmp;Move-Item -LiteralPath $tmp -Destination $resultPath -Force}
$result.runner_sha256=Hash $PSCommandPath
$result.control_sha256=Hash $control
if((Hash $Xemu)-ne$XemuSha256){throw 'xemu executable hash gate failed'}
if((Hash $seed)-ne$seedSha){throw 'Morrowind immutable seed hash gate failed'}
$launched=$false;$closed=$false
try{
 & $control -Action Init -Root $Root -SourceHdd $seed -SourceSha256 $seedSha|Out-Null
 & $control -Action Launch -Root $Root -Xemu $Xemu -XemuSha256 $XemuSha256 -Renderer $Renderer -ConfigSource $ConfigSource -ShaderCache $ShaderCache -HybridUbershaders $HybridUbershaders -Disc $Disc -PresentInterval $PresentInterval -Snapshot $snapshot|Out-Null;$launched=$true
 $deadline=[DateTime]::UtcNow.AddSeconds(60);do{try{$statusText=@(& $control -Action Status -Root $Root 2>$null)[0];$status=$statusText|ConvertFrom-Json;$ready=$status.running-eq$true-and$status.status-eq'running'}catch{$ready=$false};if(-not$ready){Start-Sleep -Milliseconds 250}}while(-not$ready-and[DateTime]::UtcNow-lt$deadline)
 if(-not$ready){throw 'Snapshot did not reach QMP running state within 60 seconds'};$result.snapshot_ready_utc=[DateTime]::UtcNow.ToString('o')
 Start-Sleep -Seconds 5;& $control -Action Capture -Root $Root -Label before-start-focus|Out-Null;$result.start_input_sent_utc=[DateTime]::UtcNow.ToString('o');& $control -Action Key -Root $Root -VirtualKey 13 -HoldMilliseconds 150|Out-Null;Start-Sleep -Seconds 2;& $control -Action Capture -Root $Root -Label before-b-focus|Out-Null;$result.b_input_sent_utc=[DateTime]::UtcNow.ToString('o');& $control -Action Key -Root $Root -VirtualKey 66 -HoldMilliseconds 150|Out-Null;Start-Sleep -Seconds 2
 & $control -Action Capture -Root $Root -Label measurement-start|Out-Null;$windowStart=[DateTime]::UtcNow;$result.measurement_started_utc=$windowStart.ToString('o');Start-Sleep -Seconds $DurationSeconds;$windowEnd=[DateTime]::UtcNow;$result.measurement_ended_utc=$windowEnd.ToString('o');$result.measurement_elapsed_seconds=($windowEnd-$windowStart).TotalSeconds;& $control -Action Capture -Root $Root -Label measurement-end|Out-Null
 & $control -Action Close -Root $Root|Out-Null;$closed=$true;$state=Get-Content -LiteralPath (Join-Path $Root 'control.json') -Raw|ConvertFrom-Json;if($state.status-ne'closed'){throw "Unexpected close status: $($state.status)"}
 $trace=Join-Path $state.launch_dir 'guest-flips.log';$rows=@();$previousNew=$null
 foreach($line in Get-Content -LiteralPath $trace){if($line-notmatch'^(\S+) nv2a_pgraph_flip_increment_write 0x([0-9a-fA-F]+) -> 0x([0-9a-fA-F]+)$'){continue};$time=[DateTimeOffset]::Parse($Matches[1]).UtcDateTime;$old=[Convert]::ToUInt32($Matches[2],16);$new=[Convert]::ToUInt32($Matches[3],16);if($null-ne$previousNew-and$old-ne$previousNew){throw 'Display-write trace continuity failed'};$previousNew=$new;if($time-ge$windowStart-and$time-le$windowEnd){$rows+=$time}}
 if($rows.Count-lt 2){throw 'Fewer than two display-write events in measurement window'};for($i=1;$i-lt$rows.Count;$i++){if($rows[$i]-le$rows[$i-1]){throw 'Display-write timestamps were not strictly increasing'}}
 $intervals=@();for($i=1;$i-lt$rows.Count;$i++){$intervals+=($rows[$i]-$rows[$i-1]).TotalMilliseconds};$sorted=@($intervals|Sort-Object);function Percentile([double]$p){$index=[Math]::Max(0,[Math]::Min($sorted.Count-1,[Math]::Ceiling($p*$sorted.Count)-1));[double]$sorted[$index]}
 $span=($rows[-1]-$rows[0]).TotalSeconds;$result.display_write_events=$rows.Count;$result.display_write_intervals=$rows.Count-1;$result.display_write_events_per_window_second=$rows.Count/$result.measurement_elapsed_seconds;$result.display_write_interval_cadence_per_second=($rows.Count-1)/$span;$result.average_fps_proxy=$result.display_write_interval_cadence_per_second;$result.frame_interval_average_ms=($intervals|Measure-Object -Average).Average;$result.frame_interval_p95_ms=Percentile 0.95;$result.frame_interval_p99_ms=Percentile 0.99;$result.frame_interval_max_ms=($intervals|Measure-Object -Maximum).Maximum;$result.frame_interval_worst_ms=@($intervals|Sort-Object -Descending|Select-Object -First 10);$result.frame_stall_threshold_ms=75;$result.frame_stall_count=@($intervals|Where-Object{$_-ge 75}).Count;$result.first_event_utc=$rows[0].ToString('o');$result.last_event_utc=$rows[-1].ToString('o')
 $beforeStartCapture=Get-Content -LiteralPath (Join-Path $state.launch_dir 'before-start-focus.capture.json') -Raw|ConvertFrom-Json;$beforeBCapture=Get-Content -LiteralPath (Join-Path $state.launch_dir 'before-b-focus.capture.json') -Raw|ConvertFrom-Json;$startCapture=Get-Content -LiteralPath (Join-Path $state.launch_dir 'measurement-start.capture.json') -Raw|ConvertFrom-Json;$endCapture=Get-Content -LiteralPath (Join-Path $state.launch_dir 'measurement-end.capture.json') -Raw|ConvertFrom-Json;if($beforeStartCapture.Status-ne'ACCEPTED'-or$beforeBCapture.Status-ne'ACCEPTED'-or$startCapture.Status-ne'ACCEPTED'-or$endCapture.Status-ne'ACCEPTED'){throw 'Automated gameplay image admission failed'};$beforeStartHash=Hash (Join-Path $state.launch_dir 'before-start-focus.png');$measurementStartHash=Hash (Join-Path $state.launch_dir 'measurement-start.png');if($beforeStartHash-eq$measurementStartHash){throw 'Morrowind Start/B route produced no image transition; unpause/gameplay admission failed'};$result.gameplay_admission='PASSED: QMP running, Start/B delivered, image transitioned, display writes advanced';$result.before_start_image_sha256=$beforeStartHash;$result.measurement_start_image_sha256=$measurementStartHash;$result.final_image_validation='PASSED';$result.final_image_sha256=Hash (Join-Path $state.launch_dir 'measurement-end.png');$result.final_image_nonblack_ratio=$endCapture.NonBlackRatio;$result.final_image_unique_sampled_colors=$endCapture.UniqueSampledColors
 if((Hash $seed)-ne$seedSha){throw 'Source HDD changed'};$exclusive=[IO.File]::Open($private,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::None);$exclusive.Dispose();Remove-Item -LiteralPath $private;if(Test-Path -LiteralPath $private){throw 'Private HDD deletion failed'};$result.private_hdd_deleted=$true;$result.seed_sha256_after=Hash $seed;$result.status='complete'
}catch{$result.status='failed';$result.error=$_.Exception.Message;if(Test-Path -LiteralPath $Root){Set-Content -LiteralPath (Join-Path $Root 'morrowind-last-error.txt') -Value ($_ | Out-String)}}finally{
 if($launched-and-not$closed){try{& $control -Action Close -Root $Root|Out-Null;$closed=$true;$result.cleanup='owned process closed after failure'}catch{$result.cleanup="uncertain process cleanup: $($_.Exception.Message)"}}
 if(Test-Path -LiteralPath $private){
  try{$exclusive=[IO.File]::Open($private,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::None);$exclusive.Dispose();Remove-Item -LiteralPath $private;if(Test-Path -LiteralPath $private){throw 'Private HDD deletion failed'};$result.private_hdd_deleted=$true;$result.cleanup=if($result.cleanup){$result.cleanup+'; private HDD deleted'}else{'private HDD deleted after failure'}}catch{$result.private_hdd_deleted=$false;$result.cleanup=if($result.cleanup){$result.cleanup+"; uncertain private HDD cleanup: $($_.Exception.Message)"}else{"uncertain private HDD cleanup: $($_.Exception.Message)"}}
 }
 if(-not(Test-Path -LiteralPath $private)){$result.private_hdd_deleted=$true}
 if(Test-Path -LiteralPath $Root){Save-Result}
}
$result|ConvertTo-Json -Depth 8;if($result.status-ne'complete'){throw "Morrowind cell failed; see $resultPath"}
