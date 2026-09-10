<#
.SYNOPSIS
Controls one hash-pinned Morrowind run on a private HDD.
.DESCRIPTION
Init clones an immutable source HDD. Launch creates a private config and either
boots it normally or restores the caller's snapshot. Every action addresses the
single process recorded in control.json. Close records identity checks and never
deletes the source HDD or source config.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('Init','Launch','Key','Capture','Status','Close')][string]$Action,
    [Parameter(Mandatory)][string]$Root,
    [string]$Xemu,
    [ValidatePattern('^$|^[0-9a-f]{64}$')][string]$XemuSha256 = '',
    [ValidateSet('VULKAN','OPENGL')][string]$Renderer = 'VULKAN',
    [ValidateSet(0,2)][int]$PresentInterval = 0,
    [string]$SourceHdd,
    [ValidatePattern('^$|^[0-9a-f]{64}$')][string]$SourceSha256 = '',
    [Parameter(Mandatory)][string]$Eeprom,
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{64}$')][string]$EepromSha256,
    [string]$BaseConfig,
    [ValidatePattern('^$|^[0-9a-f]{64}$')][string]$BaseConfigSha256 = '',
    [string]$Disc,
    [ValidatePattern('^$|^[0-9a-f]{64}$')][string]$DiscSha256 = '',
    [ValidatePattern('^$|^[A-Za-z0-9._-]+$')][string]$Snapshot = '',
    [ValidateRange(1,254)][int]$VirtualKey = 13,
    [ValidateRange(25,2000)][int]$HoldMilliseconds = 150,
    [ValidatePattern('^[A-Za-z0-9._-]+$')][string]$Label = 'capture',
    [ValidateRange(1024,65535)][int]$Port = 16653,
    [Parameter(Mandatory)][string]$HddSafetyTool,
    [Parameter(Mandatory)][string]$SendKeyTool,
    [Parameter(Mandatory)][string]$CaptureTool
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ([Diagnostics.Process]::GetCurrentProcess().SessionId -ne 1) {
    throw 'Use the Session 1 GUI pipe'
}
if (-not (Test-Path -LiteralPath $HddSafetyTool -PathType Leaf)) {
    throw "Missing HDD safety tool: $HddSafetyTool"
}
foreach ($tool in @($SendKeyTool, $CaptureTool)) {
    if (-not (Test-Path -LiteralPath $tool -PathType Leaf)) {
        throw "Missing host helper: $tool"
    }
}
. $HddSafetyTool
[void](Assert-LabPathWithoutReparse $Root)

$statePath = Join-Path $Root 'control.json'
$private = Join-Path $Root 'private-hdd.qcow2'
function Get-Sha256([string]$Path) {
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function Assert-Hash([string]$Path, [string]$Expected, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Missing ${Label}: $Path"
    }
    $actual = Get-Sha256 $Path
    if ($actual -cne $Expected) {
        throw "$Label hash mismatch: expected=$Expected actual=$actual"
    }
}
function Save-State {
    $temporary = $statePath + '.tmp'
    $script:state | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $temporary
    Move-Item -LiteralPath $temporary -Destination $statePath -Force
}
function Get-OwnedProcess {
    $all = @(Get-Process xemu -ErrorAction SilentlyContinue)
    if ($state.status -ne 'running' -or $all.Count -ne 1 -or
        $all[0].Id -ne $state.pid) {
        throw 'Exact owned xemu required'
    }
    $process = $all[0]
    if ($process.SessionId -ne 1 -or
        $process.StartTime.ToUniversalTime().ToString('o') -ne
            ([DateTime]$state.process_start_utc).ToUniversalTime().ToString('o')) {
        throw 'Process identity changed'
    }
    return $process
}
function Invoke-Qmp([string]$Command) {
    $client = [Net.Sockets.TcpClient]::new()
    $client.ReceiveTimeout = 60000
    $client.SendTimeout = 60000
    try {
        $client.Connect('127.0.0.1', [int]$state.port)
        $stream = $client.GetStream()
        $reader = [IO.StreamReader]::new($stream)
        $writer = [IO.StreamWriter]::new(
            $stream, [Text.UTF8Encoding]::new($false))
        $writer.AutoFlush = $true
        $hello = $reader.ReadLine() | ConvertFrom-Json
        if (-not $hello.QMP) { throw 'Missing QMP greeting' }
        foreach ($request in @(
            @{execute='qmp_capabilities'; id='cap'},
            @{execute=$Command; id='action'})) {
            $writer.WriteLine(($request | ConvertTo-Json -Compress))
            do {
                $line = $reader.ReadLine()
                if ($null -eq $line) { throw 'QMP EOF' }
                $response = $line | ConvertFrom-Json -AsHashtable
            } while ($response['id'] -ne $request.id)
            if ($response.ContainsKey('error')) {
                throw ($response.error | ConvertTo-Json -Compress)
            }
        }
        return $response['return']
    } finally {
        $client.Dispose()
    }
}

if ($Action -eq 'Init') {
    Assert-NoExistingXemu
    if (Test-Path -LiteralPath $Root) { throw 'Existing run root' }
    if (-not $SourceSha256) { throw 'Explicit source hash required' }
    [void](Assert-LabHddPath $SourceHdd)
    Assert-Hash $Eeprom $EepromSha256 'source EEPROM'
    $source = [IO.File]::Open(
        $SourceHdd, [IO.FileMode]::Open, [IO.FileAccess]::Read,
        [IO.FileShare]::Read)
    try {
        $sourceHash = [Convert]::ToHexString(
            [Security.Cryptography.SHA256]::HashData($source)).ToLowerInvariant()
        if ($sourceHash -cne $SourceSha256) { throw 'Source HDD hash mismatch' }
        New-Item -ItemType Directory -Path $Root | Out-Null
        $destination = [IO.File]::Open(
            $private, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write,
            [IO.FileShare]::None)
        try {
            $source.Position = 0
            $source.CopyTo($destination)
        } finally {
            $destination.Dispose()
        }
        if ((Get-Sha256 $private) -cne $SourceSha256) { throw 'Clone mismatch' }
    } finally {
        $source.Dispose()
    }
    [IO.File]::Copy($Eeprom, (Join-Path $Root 'eeprom.bin'), $false)
    $script:state = [ordered]@{
        schema_version = 2
        status = 'ready'
        source_hdd = $SourceHdd
        source_sha256 = $SourceSha256
        source_eeprom = $Eeprom
        source_eeprom_sha256 = $EepromSha256
        private_hdd = $private
        launches = 0
        port = $Port
        created_utc = [DateTime]::UtcNow.ToString('o')
    }
    Save-State
} else {
    $script:state = Get-Content -LiteralPath $statePath -Raw |
        ConvertFrom-Json -AsHashtable
    switch ($Action) {
        'Launch' {
            Assert-NoExistingXemu
            if ($state.status -notin @('ready','closed')) {
                throw 'Previous session must be safely closed'
            }
            if (-not $Xemu -or -not $XemuSha256 -or -not $BaseConfig -or
                -not $BaseConfigSha256 -or -not $Disc -or -not $DiscSha256) {
                throw 'Launch requires hash-pinned xemu, config, and disc inputs'
            }
            Assert-Hash $Xemu $XemuSha256 'xemu executable'
            Assert-Hash $BaseConfig $BaseConfigSha256 'base config'
            Assert-Hash $Disc $DiscSha256 'Morrowind disc'
            $state.launches++
            $launchDir = Join-Path $Root ('launch-' + $state.launches)
            if (Test-Path $launchDir) { throw 'Existing launch directory' }
            New-Item -ItemType Directory -Path $launchDir | Out-Null
            $text = [IO.File]::ReadAllText($BaseConfig)
            $text = $text.Replace("`r`n", "`n").Replace("`r", "`n")
            foreach ($entry in @(
                @('hdd_path', $private),
                @('eeprom_path', (Join-Path $Root 'eeprom.bin')),
                @('dvd_path', $Disc))) {
                if ([regex]::Matches($text, "(?m)^$($entry[0])\s*=").Count -ne 1) {
                    throw "Ambiguous $($entry[0]) in base config"
                }
                $text = [regex]::Replace(
                    $text, "(?m)^$($entry[0])\s*=.*$",
                    $entry[0] + " = '" + $entry[1] + "'")
            }
            if ([regex]::Matches($text, '(?m)^renderer\s*=').Count -ne 1) {
                throw 'Ambiguous renderer in base config'
            }
            $text = [regex]::Replace(
                $text, '(?m)^renderer\s*=.*$', "renderer = '$Renderer'")
            if ($PresentInterval -eq 2) {
                if ($text -match '(?m)^present_interval\s*=') {
                    if ([regex]::Matches($text, '(?m)^present_interval\s*=').Count -ne 1) {
                        throw 'Ambiguous present_interval config'
                    }
                    $text = [regex]::Replace(
                        $text, '(?m)^present_interval\s*=.*$',
                        "present_interval = $PresentInterval")
                } else {
                    if ([regex]::Matches($text, '(?m)^last_height\s*=.*$').Count -ne 1) {
                        throw 'Could not place present_interval config'
                    }
                    $text = [regex]::Replace(
                        $text, '(?m)^last_height\s*=.*$',
                        { param($match) $match.Value + "`npresent_interval = $PresentInterval" })
                }
            } elseif ($text -match '(?m)^present_interval\s*=') {
                throw 'Unexpected present_interval key in legacy-build config'
            }
            if ($text -notmatch '(?m)^setup_nvidia_profile\s*=\s*false\s*$' -or
                $text -match '(?m)^reduce_host_cpu_usage\s*=\s*true\s*$') {
                throw 'Unsafe host policy'
            }
            $config = Join-Path $launchDir 'launch-config.toml'
            [IO.File]::WriteAllText($config, $text, [Text.UTF8Encoding]::new($false))
            [IO.File]::Copy($config, (Join-Path $launchDir 'prelaunch-config.toml'), $false)
            $state.launch_dir = $launchDir
            $state.exe = $Xemu
            $state.exe_sha256 = $XemuSha256
            $state.renderer = $Renderer
            $state.base_config = $BaseConfig
            $state.base_config_sha256 = $BaseConfigSha256
            $state.disc = $Disc
            $state.disc_sha256 = $DiscSha256
            $state.restore_snapshot = $Snapshot
            $state.prelaunch_sha256 = Get-Sha256 (Join-Path $launchDir 'prelaunch-config.toml')
            $listener = [Net.Sockets.TcpListener]::new(
                [Net.IPAddress]::Loopback, [int]$state.port)
            try { $listener.Start() } finally { $listener.Stop() }
            $trace = Join-Path $launchDir 'guest-flips.log'
            $arguments = @(
                '-config_path', $config,
                '-qmp', "tcp:127.0.0.1:$($state.port),server=on,wait=off",
                '-trace', "enable=nv2a_pgraph_flip_increment_write,file=$trace",
                '-msg', 'timestamp=on')
            if ($Snapshot) { $arguments += @('-loadvm', $Snapshot) }
            $process = $null
            try {
                $process = Start-Process -FilePath $Xemu -ArgumentList $arguments `
                    -WorkingDirectory (Split-Path $Xemu) -WindowStyle Normal -PassThru `
                    -RedirectStandardOutput (Join-Path $launchDir 'stdout.log') `
                    -RedirectStandardError (Join-Path $launchDir 'stderr.log')
                $state.pid = $process.Id
                $state.process_start_utc = $process.StartTime.ToUniversalTime().ToString('o')
                $state.status = 'running'
                Save-State
            } catch {
                if ($null -ne $process -and -not $process.HasExited) {
                    $process.Kill($true)
                    [void]$process.WaitForExit(15000)
                }
                throw
            }
        }
        'Key' {
            $process = Get-OwnedProcess
            & $SendKeyTool -ProcessId $process.Id -VirtualKey $VirtualKey `
                -HoldMilliseconds $HoldMilliseconds
        }
        'Capture' {
            $process = Get-OwnedProcess
            Add-Type -AssemblyName Microsoft.VisualBasic
            [void][Microsoft.VisualBasic.Interaction]::AppActivate($process.Id)
            Start-Sleep -Milliseconds 200
            & $CaptureTool -ProcessId $process.Id `
                -OutputPath (Join-Path $state.launch_dir ($Label + '.png')) `
                -MetadataPath (Join-Path $state.launch_dir ($Label + '.capture.json'))
        }
        'Status' {
            $process = Get-OwnedProcess
            Invoke-Qmp 'query-status' | ConvertTo-Json -Compress
        }
        'Close' {
            $process = Get-OwnedProcess
            $requested = $process.CloseMainWindow()
            $forced = $false
            if (-not $process.WaitForExit(15000)) {
                $forced = $true
                $process = Get-OwnedProcess
                $process.Kill($true)
                if (-not $process.WaitForExit(15000)) {
                    throw 'Owned xemu failed to close'
                }
            }
            foreach ($path in @($private, (Join-Path $Root 'eeprom.bin'))) {
                $exclusive = [IO.File]::Open(
                    $path, [IO.FileMode]::Open, [IO.FileAccess]::Read,
                    [IO.FileShare]::None)
                $exclusive.Dispose()
            }
            [IO.File]::Copy(
                (Join-Path $state.launch_dir 'launch-config.toml'),
                (Join-Path $state.launch_dir 'postexit-config.toml'), $false)
            if ((Get-Sha256 (Join-Path $state.launch_dir 'prelaunch-config.toml')) -cne
                $state.prelaunch_sha256) { throw 'Prelaunch config changed' }
            Assert-Hash $state.source_hdd $state.source_sha256 'source HDD after run'
            Assert-Hash $state.source_eeprom $state.source_eeprom_sha256 'source EEPROM after run'
            Assert-Hash $state.base_config $state.base_config_sha256 'base config after run'
            Assert-Hash $state.disc $state.disc_sha256 'Morrowind disc after run'
            $state.private_sha256 = Get-Sha256 $private
            $state.eeprom_sha256 = Get-Sha256 (Join-Path $Root 'eeprom.bin')
            $state.status = if ($forced) { 'forced-closed' } else { 'closed' }
            $state.closed_utc = [DateTime]::UtcNow.ToString('o')
            Save-State
        }
    }
}

[ordered]@{
    at_utc = [DateTime]::UtcNow.ToString('o')
    action = $Action
    snapshot = $Snapshot
    key = $VirtualKey
    renderer = $Renderer
    present_interval = $PresentInterval
} | ConvertTo-Json -Compress | Add-Content -LiteralPath (Join-Path $Root 'actions.jsonl')
$state | ConvertTo-Json -Depth 8
