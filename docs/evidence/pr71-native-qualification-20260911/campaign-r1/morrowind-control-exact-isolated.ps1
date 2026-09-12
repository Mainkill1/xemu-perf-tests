<#
.SYNOPSIS
Controls one hash-pinned Morrowind snapshot session on private state.
.DESCRIPTION
Creates a private HDD copy, launches an exact xemu executable with the selected
renderer, sends keys, captures the window, queries QMP, and closes only the
owned process. Run through the Session 1 GUI pipe.
.PARAMETER Action
Operation to perform: Init, Launch, Key, Capture, Status, or Close.
.PARAMETER Root
Unique run directory containing the private HDD and durable control state.
.PARAMETER Xemu
Exact executable used by Launch.
.PARAMETER XemuSha256
Required SHA-256 of Xemu.
.PARAMETER Renderer
VULKAN or OPENGL.
.PARAMETER PresentInterval
Presentation interval written to the launch config. Use 2 only for the
half-refresh candidate; use 0 to omit the key for builds without the option.
.EXAMPLE
.\morrowind-control-active-lru.ps1 -Action Launch -Root C:\xemu-lab\runs\mw-01 -Xemu C:\build\xemu.exe -XemuSha256 '<sha256>' -Renderer VULKAN -Snapshot vm-20260905015459
#>
[CmdletBinding()]
param(
 [Parameter(Mandatory)][ValidateSet('Init','Launch','Key','Capture','Status','Close')][string]$Action,
 [Parameter(Mandatory)][string]$Root,
 [string]$Xemu,
 [ValidatePattern('^$|^[0-9a-f]{64}$')][string]$XemuSha256='',
 [ValidateSet('VULKAN','OPENGL')][string]$Renderer='VULKAN',
 [Parameter(Mandatory=$false)][string]$ConfigSource='',
 [ValidateSet('Enabled','Disabled')][string]$ShaderCache='Enabled',
 [ValidateSet('Off','On')][string]$HybridUbershaders='Off',
 [string]$Disc='',
 [ValidateSet(0,2)][int]$PresentInterval=0,
 [string]$SourceHdd,
 [ValidatePattern('^$|^[0-9a-f]{64}$')][string]$SourceSha256='',
 [ValidatePattern('^$|^[A-Za-z0-9._-]+$')][string]$Snapshot='',
 [ValidateRange(1,254)][int]$VirtualKey=13,
 [ValidateRange(25,2000)][int]$HoldMilliseconds=150,
 [ValidatePattern('^[A-Za-z0-9._-]+$')][string]$Label='capture',
 [ValidateRange(1024,65535)][int]$Port=16653
)
$ErrorActionPreference='Stop'; Set-StrictMode -Version Latest
if([Diagnostics.Process]::GetCurrentProcess().SessionId-ne 1){throw 'Use the Session 1 GUI pipe'}
. 'C:\xemu-lab\runs\tools-881c522d26e0-pr03\hdd-safety.ps1'
[void](Assert-LabPathWithoutReparse $Root)
$statePath=Join-Path $Root 'control.json'; $private=Join-Path $Root 'private-hdd.qcow2'
function Hash([string]$p){(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()}
function Save-State{$tmp=$statePath+'.tmp';$script:m|ConvertTo-Json -Depth 10|Set-Content -LiteralPath $tmp;Move-Item -LiteralPath $tmp -Destination $statePath -Force}
function Owned{
 $all=@(Get-Process xemu -ErrorAction SilentlyContinue)
 if($m.status-ne'running'-or$all.Count-ne 1-or$all[0].Id-ne$m.pid){throw 'Exact owned xemu required'}
 $p=$all[0]
 if($p.SessionId-ne 1-or$p.StartTime.ToUniversalTime().ToString('o')-ne([DateTime]$m.process_start_utc).ToUniversalTime().ToString('o')){throw 'Process identity changed'}
 return $p
}
function Qmp([string]$Command){
 $client=[Net.Sockets.TcpClient]::new();$client.ReceiveTimeout=60000;$client.SendTimeout=60000
 try{
  $client.Connect('127.0.0.1',[int]$m.port);$stream=$client.GetStream()
  $reader=[IO.StreamReader]::new($stream);$writer=[IO.StreamWriter]::new($stream,[Text.UTF8Encoding]::new($false));$writer.AutoFlush=$true
  $hello=$reader.ReadLine()|ConvertFrom-Json;if(-not$hello.QMP){throw 'Missing QMP greeting'}
  foreach($request in @(@{execute='qmp_capabilities';id='cap'},@{execute=$Command;id='action'})){
   $writer.WriteLine(($request|ConvertTo-Json -Compress))
   do{$line=$reader.ReadLine();if($null-eq$line){throw 'QMP EOF'};$response=$line|ConvertFrom-Json -AsHashtable}while($response['id']-ne$request.id)
   if($response.ContainsKey('error')){throw($response.error|ConvertTo-Json -Compress)}
  }
  return $response['return']
 }finally{$client.Dispose()}
}
if($Action-eq'Init'){
 Assert-NoExistingXemu
 if(Test-Path -LiteralPath $Root){throw 'Existing run root'}
 if(-not$SourceSha256){throw 'Explicit source hash required'}
 [void](Assert-LabHddPath $SourceHdd)
 $guard=[IO.File]::Open($SourceHdd,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
 try{
  $h=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($guard)).ToLowerInvariant();if($h-ne$SourceSha256){throw 'Source HDD hash mismatch'}
  New-Item -ItemType Directory -Path $Root|Out-Null
  $out=[IO.File]::Open($private,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
  try{$guard.Position=0;$guard.CopyTo($out)}finally{$out.Dispose()}
  if((Hash $private)-ne$SourceSha256){throw 'Clone mismatch'}
 }finally{$guard.Dispose()}
 [IO.File]::Copy('C:\Users\codex\AppData\Roaming\xemu\xemu\eeprom.bin',"$Root\eeprom.bin",$false)
 $script:m=@{schema_version=1;status='ready';source_hdd=$SourceHdd;source_sha256=$SourceSha256;private_hdd=$private;launches=0;port=$Port;created_utc=[DateTime]::UtcNow.ToString('o')};Save-State
}else{
 $script:m=Get-Content -LiteralPath $statePath -Raw|ConvertFrom-Json -AsHashtable
 switch($Action){
  Launch{
   Assert-NoExistingXemu
   if($m.status-notin@('ready','closed')){throw 'Previous session must be safely closed'}
   if(-not$Xemu-or-not$XemuSha256){throw 'Launch requires Xemu and XemuSha256'}
   if((Hash $Xemu)-ne$XemuSha256){throw 'Wrong executable'}
   $m.launches++;$dir=Join-Path $Root ('launch-'+$m.launches);if(Test-Path $dir){throw 'Existing launch directory'};New-Item -ItemType Directory -Path $dir|Out-Null
   $configSource=if($ConfigSource){$ConfigSource}else{'C:\xemu-lab\captures\pgr2-exclusive\configs\'+$Renderer.ToLowerInvariant()+'.toml'}
   $text=[IO.File]::ReadAllText($configSource)
   $text=$text.Replace("`r`n","`n").Replace("`r","`n")
   $discPath=if($Disc){$Disc}else{'C:\xemu-lab\games\Elder Scrolls III, The - Morrowind - Game of the Year Edition (USA).iso'}
   foreach($entry in @(@('hdd_path',$private),@('eeprom_path',"$Root\eeprom.bin"),@('dvd_path',$discPath))){
    if([regex]::Matches($text,"(?m)^$($entry[0])\s*=").Count-ne 1){throw 'Ambiguous config input'}
    $text=[regex]::Replace($text,"(?m)^$($entry[0])\s*=.*$",$entry[0]+" = '"+$entry[1]+"'")
   }
   $cacheValue=if($ShaderCache-eq'Enabled'){'true'}else{'false'}; $hybridValue=if($HybridUbershaders-eq'On'){'true'}else{'false'}
   if($text-notmatch'(?m)^\[perf\]'){ $text += "`n`n[perf]`ncache_shaders = $cacheValue" }else{ throw 'Config must not contain a duplicate perf section' }
   if($text-notmatch'(?m)^\[tweaks\]'){ $text += "`n`n[tweaks]`nvk_hybrid_ubershaders = $hybridValue" }else{ throw 'Config must not contain a duplicate tweaks section' }
   if($PresentInterval-eq 2){
    if($text-match'(?m)^present_interval\s*='){
     if([regex]::Matches($text,'(?m)^present_interval\s*=').Count-ne 1){throw 'Ambiguous present_interval config'}
     $text=[regex]::Replace($text,'(?m)^present_interval\s*=.*$',"present_interval = $PresentInterval")
    }else{
     if([regex]::Matches($text,'(?m)^last_height\s*=.*$').Count-ne 1){throw 'Could not place present_interval config'}
     $text=[regex]::Replace($text,'(?m)^last_height\s*=.*$',{param($match) $match.Value+"`npresent_interval = $PresentInterval"})
    }
    if([regex]::Matches($text,"(?m)^present_interval\s*=\s*$PresentInterval\s*$").Count-ne 1){throw 'present_interval verification failed'}
   }elseif($text-match'(?m)^present_interval\s*='){throw 'Unexpected present_interval key in legacy-build config'}
   if($text-notmatch'(?m)^setup_nvidia_profile\s*=\s*false\s*$'-or$text-match'(?m)^reduce_host_cpu_usage\s*=\s*true\s*$'){throw 'Unsafe host policy'}
   $config=Join-Path $dir 'launch-config.toml';[IO.File]::WriteAllText($config,$text,[Text.UTF8Encoding]::new($false));[IO.File]::Copy($config,"$dir\prelaunch-config.toml",$false)
   $m.launch_dir=$dir;$m.exe=$Xemu;$m.exe_sha256=$XemuSha256;$m.renderer=$Renderer;$m.present_interval_requested=$PresentInterval;$m.restore_snapshot=$Snapshot;$m.prelaunch_sha256=Hash "$dir\prelaunch-config.toml"
   $listener=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,[int]$m.port);try{$listener.Start()}finally{$listener.Stop()}
   $trace=Join-Path $dir 'guest-flips.log';$argv=@('-config_path',$config,'-qmp',"tcp:127.0.0.1:$($m.port),server=on,wait=off",'-trace',"enable=nv2a_pgraph_flip_increment_write,file=$trace",'-msg','timestamp=on');if($Snapshot){$argv+=@('-loadvm',$Snapshot)}
   $profileRootFull=Join-Path (Split-Path -Parent $Xemu) 'profile-env';$roamingRoot=Join-Path $profileRootFull 'Roaming';$localRoot=Join-Path $profileRootFull 'Local';New-Item -ItemType Directory -Path $roamingRoot,$localRoot -Force|Out-Null
   $savedAppData=[Environment]::GetEnvironmentVariable('APPDATA','Process');$savedLocalAppData=[Environment]::GetEnvironmentVariable('LOCALAPPDATA','Process')
   try{[Environment]::SetEnvironmentVariable('APPDATA',$roamingRoot,'Process');[Environment]::SetEnvironmentVariable('LOCALAPPDATA',$localRoot,'Process');$p=Start-Process -FilePath $Xemu -ArgumentList $argv -WorkingDirectory (Split-Path $Xemu) -WindowStyle Normal -PassThru -Environment @{APPDATA=$roamingRoot;LOCALAPPDATA=$localRoot} -RedirectStandardOutput "$dir\stdout.log" -RedirectStandardError "$dir\stderr.log"}finally{[Environment]::SetEnvironmentVariable('APPDATA',$savedAppData,'Process');[Environment]::SetEnvironmentVariable('LOCALAPPDATA',$savedLocalAppData,'Process')}
   $m.pid=$p.Id;$m.process_start_utc=$p.StartTime.ToUniversalTime().ToString('o');$m.status='running';Save-State
  }
  Key{$p=Owned;& (Join-Path $PSScriptRoot 'send-xemu-key.ps1') -ProcessId $p.Id -VirtualKey $VirtualKey -HoldMilliseconds $HoldMilliseconds}
  Capture{$p=Owned;Add-Type -AssemblyName Microsoft.VisualBasic;[void][Microsoft.VisualBasic.Interaction]::AppActivate($p.Id);Start-Sleep -Milliseconds 200;& 'C:\xemu-lab\suite-eng523-9ff9af9\capture-xemu-window.ps1' -ProcessId $p.Id -OutputPath (Join-Path $m.launch_dir ($Label+'.png')) -MetadataPath (Join-Path $m.launch_dir ($Label+'.capture.json'))}
  Status{$p=Owned;Qmp 'query-status'|ConvertTo-Json -Compress}
  Close{
   $p=Owned;$requested=$p.CloseMainWindow();$forced=$false;if(-not$p.WaitForExit(15000)){$forced=$true;$p=Owned;$p.Kill($true);if(-not$p.WaitForExit(15000)){throw 'Owned xemu failed to close'}}
   foreach($path in @($private,"$Root\eeprom.bin")){$s=[IO.File]::Open($path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::None);$s.Dispose()}
   [IO.File]::Copy((Join-Path $m.launch_dir 'launch-config.toml'),(Join-Path $m.launch_dir 'postexit-config.toml'),$false)
   if((Hash (Join-Path $m.launch_dir 'prelaunch-config.toml'))-ne$m.prelaunch_sha256){throw 'Prelaunch config changed'};if((Hash $m.source_hdd)-ne$m.source_sha256){throw 'Source HDD changed'}
   $m.private_sha256=Hash $private;$m.eeprom_sha256=Hash "$Root\eeprom.bin";$m.status=if($forced){'forced-closed'}else{'closed'};$m.closed_utc=[DateTime]::UtcNow.ToString('o');Save-State
  }
 }
}
@{at_utc=[DateTime]::UtcNow.ToString('o');action=$Action;snapshot=$Snapshot;key=$VirtualKey;renderer=$Renderer;present_interval=$PresentInterval}|ConvertTo-Json -Compress|Add-Content -LiteralPath "$Root\actions.jsonl"
$m|ConvertTo-Json -Depth 8
