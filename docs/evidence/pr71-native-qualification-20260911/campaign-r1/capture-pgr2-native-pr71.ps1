# Derived from the proven PGR2 capture runner. Gameplay launch and key
# sequences are unchanged. TraceProfile None suppresses WPR/ETL collection.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Xemu,

    # This must be an immutable, workload-specific qcow2 containing the
    # requested snapshot (for Snapshot mode) or the clean game HDD seed (for
    # FreshBoot). The run never launches against this file directly.
    [Parameter(Mandatory = $true)]
    [string]$SeedHdd,

    # Canonical renderer-specific config supplied by the release wrapper.
    # Capture mode intentionally has no APPDATA/global-config fallback.
    [Parameter(Mandatory = $true)]
    [string]$BaseConfig,

    [ValidateSet('Snapshot', 'FreshBoot')]
    [string]$LaunchMode = 'Snapshot',

    [string]$Snapshot = 'vm-20260901105001',

    [string]$Game = 'PGR2',

    [string]$Disc = 'C:\xemu-lab\games\Project Gotham Racing 2 (USA, Asia) (En,Ja,Fr,De,Es,It,Zh,Ko).iso',

    [string]$CaptureRoot = 'C:\xemu-lab\captures\pgr2-wpr',

    [string]$BuildResultName = 'PGR2-RESULT.json',

    [string]$Mode = 'PGR2-LAGPOINT-SNAPSHOT-WPR',

    [ValidateSet('OPENGL', 'VULKAN')]
    [string]$Renderer = 'VULKAN',

    # These restart-only settings are written to the run-local config. Every
    # native cell therefore records the exact cache and ubershader state.
    [ValidateSet('Enabled', 'Disabled')]
    [string]$ShaderCache = 'Enabled',

    [ValidateSet('Off', 'On')]
    [string]$HybridUbershaders = 'Off',

    [ValidateRange(1, 10)]
    [int]$SurfaceScale = 1,

    [ValidateSet(0, 4, 8, 16)]
    [int]$VertexStagingInitialMiB = 0,

    [ValidateSet('Enabled', 'Disabled')]
    [string]$ReuseIdenticalIndexPayloads = 'Disabled',

    [ValidateSet('Enabled', 'Disabled')]
    [string]$ExpandDescriptorSets = 'Disabled',

    [ValidateSet('Enabled', 'Disabled')]
    [string]$TlbDirtyHostPageFilter = 'Disabled',

    [ValidateSet('Enabled', 'Disabled')]
    [string]$SkipEquivalentTextureScaleUpdates = 'Disabled',

    [ValidateRange(10, 300)]
    [int]$DurationSeconds = 60,

    [ValidateRange(0, 300)]
    [int]$WarmupSeconds = 30,

    [ValidateRange(20, 1000)]
    [int]$FrameStallMilliseconds = 75,

    [ValidateSet('None', 'CpuScheduler', 'Gpu', 'Syscalls')]
    [string]$TraceProfile = 'None',

    [ValidateSet('Startup', 'SteadyState')]
    [string]$TraceStartMode = 'Startup',

    [ValidateSet('Enabled', 'Disabled')]
    [string]$VkTelemetry = 'Disabled',

    [ValidateSet('Enabled', 'Disabled')]
    [string]$PresentMonMode = 'Enabled',

    [string]$RunId = ('pgr2-lagpoint-' + (Get-Date -Format 'yyyyMMdd-HHmmss')),

    [string]$Wpr = 'C:\xemu-lab\tools\wpt-26100\wpr.exe',

    [string]$Xperf = 'C:\xemu-lab\tools\wpt-26100\xperf.exe',

    [string]$WpaExporter = 'C:\xemu-lab\tools\wpt-26100\wpaexporter.exe',

    [string]$WpaProfile = '',

    [string]$SyscallWprp = 'C:\xemu-lab\suite\xemu-syscalls.wprp',

    [string]$SymbolPath = '',

    [switch]$RequirePdb,

    [string]$BuildManifest = '',

    [switch]$RequireSourceOwnership,

    [string]$Dumpbin = '',

    [string]$PresentMon = 'C:\xemu-lab\tools\presentmon\PresentMon.exe',

    [ValidateRange(1, 255)]
    [int]$ResumeVirtualKey = 65,

    [ValidateRange(1, 10)]
    [int]$ResumeDelaySeconds = 2,

    [ValidateRange(1, 4)]
    [int]$ResumeKeyCount = 1,

    # Optional snapshot-specific steps in KEY-DELAY form, for example B-3.
    # When supplied, this replaces the legacy Enter + resume-key sequence.
    [string[]]$SnapshotKeySequence = @(),

    [ValidateRange(0, 60)]
    [int]$FreshBootBiosDelaySeconds = 10,

    [string[]]$FreshBootKeySequence = @(
        'A-3',
        'A-10',
        'A-2',
        'A-2',
        'F-2',
        'A-2',
        'A-2',
        'A-2',
        'A-2',
        'A-2',
        'A-7'
    ),

    [string]$ScreenshotTool = 'C:\xemu-lab\suite\capture-full-xemu-window.ps1',

    [string]$QemuImg = 'C:\xemu-lab\tools\qemu-img.exe',

    [Parameter(Mandatory = $true)]
    [string]$ProfileRoot,

    [switch]$RequireSpirvSummary
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$principal = New-Object Security.Principal.WindowsPrincipal(
    [Security.Principal.WindowsIdentity]::GetCurrent()
)
if ([Diagnostics.Process]::GetCurrentProcess().SessionId -ne 1) {
    throw 'Gameplay capture must run in interactive Session 1.'
}
if ($TraceProfile -ne 'None' -and -not $principal.IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'WPR capture requires an elevated interactive PowerShell session.'
}

$suiteRoot = $PSScriptRoot
$buildDirectory = Split-Path -Parent $Xemu
$buildResult = Join-Path $buildDirectory $BuildResultName
$runDir = Join-Path $CaptureRoot $RunId
$profileSlug = $TraceProfile.ToLowerInvariant()
$etl = if ($TraceProfile -eq 'None') { $null } else {
    Join-Path $runDir (($Game.ToLowerInvariant()) + '-' + $profileSlug + '.etl')
}
$gpuCsv = Join-Path $runDir 'nvidia-gpu.csv'
$flipLog = Join-Path $runDir 'xemu-flips.csv'
$guestTraceLog = Join-Path $runDir 'guest-flips.log'
$frameLog = Join-Path $runDir 'xemu-frames.csv'
$frameLogMeasured = Join-Path $runDir 'xemu-frames-measured.csv'
$eventLog = Join-Path $runDir 'xemu-events.jsonl'
$vkPerfLog = Join-Path $runDir 'xemu-vk-perf.jsonl'
$vkPerfMeasured = Join-Path $runDir 'xemu-vk-perf-measured.jsonl'
$vkPerfSummary = Join-Path $runDir 'xemu-vk-perf-summary.json'
$presentMonCsv = Join-Path $runDir 'presentmon.csv'
$presentMonStdout = Join-Path $runDir 'presentmon-stdout.txt'
$presentMonStderr = Join-Path $runDir 'presentmon-stderr.txt'
$screenshot = Join-Path $runDir 'capture-start.png'
$runInfo = Join-Path $runDir 'run-info.txt'
$completeMarker = Join-Path $runDir 'complete.json'
$gracefulShutdownPath = Join-Path $runDir 'graceful-shutdown.json'
$launchStdout = Join-Path $runDir 'launch-stdout.txt'
$launchStderr = Join-Path $runDir 'launch-stderr.txt'
$traceStats = Join-Path $runDir 'trace-stats.txt'
$symbolPreflight = Join-Path $runDir 'symbol-preflight.txt'
$frameStats = Join-Path $runDir 'frame-time-summary.json'
$buildIdentity = Join-Path $runDir 'build-identity.json'
$analysisFilter = Join-Path $runDir 'analysis-filter.json'
$freshBootInputLog = Join-Path $runDir 'fresh-boot-input.jsonl'
$wpaExportDirectory = Join-Path $runDir 'wpa-exports'
$configPath = Join-Path $runDir 'launch-config.toml'
$hddLifecyclePath = Join-Path $runDir 'hdd-lifecycle.json'
$privateHdd = Join-Path $runDir 'private-hdd.qcow2'
$configCopy = Join-Path $runDir 'xemu.toml'
$vkTelemetryActive = $Renderer -eq 'VULKAN' -and $VkTelemetry -eq 'Enabled'
$effectiveTraceStartMode = if ($TraceProfile -eq 'None') {
    'Disabled'
} elseif ($TraceProfile -eq 'Syscalls') {
    'SteadyState'
} else {
    $TraceStartMode
}
$bundledPython = 'C:\\xemu-lab\\suite\\python313\\python.exe'
$python = if (Test-Path -LiteralPath $bundledPython -PathType Leaf) {
    $bundledPython
} else {
    $pythonCommand = Get-Command python -CommandType Application `
        -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($pythonCommand) { $pythonCommand.Source } else { $null }
}
if (Test-Path -LiteralPath $runDir) {
    throw "Run directory already exists; use a unique -RunId: $runDir"
}
New-Item -ItemType Directory -Path $runDir | Out-Null

foreach ($required in @(
        $Xemu,
        $disc,
        $ScreenshotTool,
        (Join-Path $suiteRoot 'start-retail-snapshot.ps1'),
        (Join-Path $suiteRoot 'send-xemu-key.ps1'),
        (Join-Path $suiteRoot 'invoke-xemu-timed-key-sequence.ps1'),
        (Join-Path $suiteRoot 'summarize-vk-perf.py'),
        $BaseConfig,
        $SeedHdd)) {
        if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
            throw "Required file was not found: $required"
        }
    }
if ($TraceProfile -ne 'None') {
    foreach ($traceTool in @($Wpr, $Xperf)) {
        if (-not (Test-Path -LiteralPath $traceTool -PathType Leaf)) {
            throw "Required trace tool was not found: $traceTool"
        }
    }
}
if ($WpaProfile -and $TraceProfile -eq 'None') {
    throw 'WPA export requires an enabled WPR trace profile.'
}
if ($LaunchMode -eq 'Snapshot' -and
    -not (Test-Path -LiteralPath $QemuImg -PathType Leaf)) {
    throw "Snapshot validation requires qemu-img: $QemuImg"
}
if ($PresentMonMode -eq 'Enabled' -and
    -not (Test-Path -LiteralPath $PresentMon -PathType Leaf)) {
    throw "PresentMon was not found: $PresentMon"
}
if ($vkTelemetryActive -and -not $python) {
    throw 'Vulkan telemetry requires bundled python313 or python.exe on PATH.'
}
if ($TraceProfile -eq 'Syscalls' -and
    -not (Test-Path -LiteralPath $SyscallWprp -PathType Leaf)) {
    throw "Syscall WPR profile was not found: $SyscallWprp"
}
if ($WpaProfile -and
    -not (Test-Path -LiteralPath $WpaProfile -PathType Leaf)) {
    throw "WPA export profile was not found: $WpaProfile"
}
$pdb = [System.IO.Path]::ChangeExtension($Xemu, '.pdb')
if ($RequirePdb -and -not (Test-Path -LiteralPath $pdb -PathType Leaf)) {
    throw "Symbol capture requires a matching PDB beside xemu.exe: $pdb"
}

$resolvedDumpbin = $null
$pdbMatchVerified = $false
if ($RequirePdb) {
    if ($Dumpbin) {
        if (-not (Test-Path -LiteralPath $Dumpbin -PathType Leaf)) {
            throw "dumpbin was not found: $Dumpbin"
        }
        $resolvedDumpbin = (Resolve-Path -LiteralPath $Dumpbin).Path
    } else {
        $command = Get-Command dumpbin.exe -ErrorAction SilentlyContinue
        if ($command) {
            $resolvedDumpbin = $command.Source
        } else {
            $vswhere = Join-Path ${env:ProgramFiles(x86)} `
                'Microsoft Visual Studio\Installer\vswhere.exe'
            if (Test-Path -LiteralPath $vswhere -PathType Leaf) {
                $vsRoot = (& $vswhere -latest -products '*' `
                    -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 `
                    -property installationPath | Select-Object -First 1)
                if ($vsRoot) {
                    $candidate = Get-ChildItem `
                        (Join-Path $vsRoot 'VC\Tools\MSVC') `
                        -Recurse -File -Filter dumpbin.exe `
                        -ErrorAction SilentlyContinue |
                        Where-Object FullName -Match `
                            '\\bin\\Hostx64\\x64\\dumpbin\.exe$' |
                        Sort-Object FullName -Descending |
                        Select-Object -First 1
                    if ($candidate) {
                        $resolvedDumpbin = $candidate.FullName
                    }
                }
            }
        }
    }
    if (-not $resolvedDumpbin) {
        throw 'Symbol capture requires dumpbin to verify the executable/PDB identity.'
    }

    $symbolStdout = [System.IO.Path]::GetTempFileName()
    $symbolStderr = [System.IO.Path]::GetTempFileName()
    try {
        $symbolCheck = Start-Process -FilePath $resolvedDumpbin `
            -ArgumentList @('/pdbpath:verbose', $Xemu) `
            -WindowStyle Hidden -Wait -PassThru `
            -RedirectStandardOutput $symbolStdout `
            -RedirectStandardError $symbolStderr
        $symbolText = @(
            (Get-Content -LiteralPath $symbolStdout -Raw `
                -ErrorAction SilentlyContinue)
            (Get-Content -LiteralPath $symbolStderr -Raw `
                -ErrorAction SilentlyContinue)
        ) -join "`n"
        $symbolText | Set-Content -LiteralPath $symbolPreflight -Encoding utf8
    } finally {
        Remove-Item -LiteralPath $symbolStdout, $symbolStderr -Force `
            -ErrorAction SilentlyContinue
    }
    if (-not $symbolCheck -or $symbolCheck.ExitCode -ne 0) {
        throw "dumpbin could not validate the PDB; see $symbolPreflight"
    }
    $expectedFoundLine = "PDB file found at '$pdb'"
    $pdbMatchVerified = $symbolText.IndexOf(
        $expectedFoundLine, [StringComparison]::OrdinalIgnoreCase
    ) -ge 0
    if (-not $pdbMatchVerified) {
        throw "PDB does not match xemu.exe; see $symbolPreflight"
    }
}

Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class Pgr2WprWindow {
    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr window);
}
'@

function Get-Sha256([string]$Path) {
    $stream = [System.IO.File]::OpenRead($Path)
    try {
        $sha = [System.Security.Cryptography.SHA256]::Create()
        try {
            return ([BitConverter]::ToString($sha.ComputeHash($stream)) -replace '-', '').ToLowerInvariant()
        } finally {
            $sha.Dispose()
        }
    } finally {
        $stream.Dispose()
    }
}

function Write-HddLifecycle {
    $hddLifecycle | ConvertTo-Json -Depth 5 |
        Set-Content -LiteralPath $hddLifecyclePath -Encoding utf8
}

function Assert-SnapshotPresent([string]$Path, [string]$Name) {
    $listing = @(& $QemuImg snapshot -l $Path 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw "qemu-img could not list snapshots in the private HDD: $($listing -join ' ')"
    }
    $escaped = [regex]::Escape($Name)
    if (-not (@($listing | Where-Object {
                    [string]$_ -match ('(^|\s)' + $escaped + '(\s|$)')
                }).Count -gt 0)) {
        throw "Private HDD does not contain required snapshot '$Name'."
    }
}

function Wait-HddExclusive([string]$Path, [int]$TimeoutSeconds = 30) {
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        try {
            $stream = [System.IO.File]::Open(
                $Path,
                [System.IO.FileMode]::Open,
                [System.IO.FileAccess]::Read,
                [System.IO.FileShare]::None
            )
            $stream.Dispose()
            return
        } catch {
            Start-Sleep -Milliseconds 250
        }
    }
    throw "Timed out waiting for exclusive access to private HDD: $Path"
}

function Set-ConfigValue(
    [System.Collections.Generic.List[string]]$Lines,
    [string]$Key,
    [string]$Value
) {
    if ($Value.Contains("'")) {
        throw "Configuration value for $Key cannot contain a single quote: $Value"
    }
    $found = $false
    for ($i = 0; $i -lt $Lines.Count; $i++) {
        if ($Lines[$i] -match ('^\s*' + [regex]::Escape($Key) + '\s*=')) {
            $Lines[$i] = "$Key = '$Value'"
            $found = $true
            break
        }
    }
    if (-not $found) {
        throw "Required configuration key was not found: $Key"
    }
}

function Assert-BaseConfigPolicy([string]$Path) {
    $lines = [System.IO.File]::ReadAllLines($Path)
    $nvidiaMatches = @($lines | Where-Object {
            [string]$_ -match '^\s*setup_nvidia_profile\s*=\s*(true|false)\s*(#.*)?$'
        })
    if ($nvidiaMatches.Count -ne 1 -or
        [string]$nvidiaMatches[0] -notmatch
        '^\s*setup_nvidia_profile\s*=\s*false\s*(#.*)?$') {
        throw "Base config must explicitly set setup_nvidia_profile = false: $Path"
    }
    if (@($lines | Where-Object {
                [string]$_ -match '^\s*reduce_host_cpu_usage\s*=\s*true\s*(#.*)?$'
            }).Count -gt 0) {
        throw "Base config must not enable reduce_host_cpu_usage: $Path"
    }
}

function Set-RendererValue(
    [System.Collections.Generic.List[string]]$Lines,
    [string]$Renderer
) {
    for ($i = 0; $i -lt $Lines.Count; $i++) {
        if ($Lines[$i] -match '^\s*renderer\s*=') {
            $Lines[$i] = "renderer = '$Renderer'"
            return
        }
    }
    $displaySection = $Lines.IndexOf('[display]')
    if ($displaySection -lt 0) {
        throw 'Base config must contain a [display] section for renderer selection.'
    }
    $Lines.Insert($displaySection + 1, "renderer = '$Renderer'")
}

function Set-TomlBoolean(
    [System.Collections.Generic.List[string]]$Lines,
    [string]$Section,
    [string]$Key,
    [bool]$Value
) {
    $sectionStart = -1
    for ($i = 0; $i -lt $Lines.Count; $i++) {
        if ($Lines[$i] -match ('^\s*\[' + [regex]::Escape($Section) + '\]\s*$')) {
            $sectionStart = $i
            break
        }
    }
    $literal = if ($Value) { 'true' } else { 'false' }
    if ($sectionStart -ge 0) {
        for ($i = $sectionStart + 1; $i -lt $Lines.Count; $i++) {
            if ($Lines[$i] -match '^\s*\[') { break }
            if ($Lines[$i] -match ('^\s*' + [regex]::Escape($Key) + '\s*=')) {
                $Lines[$i] = "$Key = $literal"
                return
            }
        }
        $insertAt = $sectionStart + 1
        while ($insertAt -lt $Lines.Count -and $Lines[$insertAt] -notmatch '^\s*\[') {
            $insertAt++
        }
        $Lines.Insert($insertAt, "$Key = $literal")
        return
    }
    if ($Lines.Count -gt 0 -and $Lines[$Lines.Count - 1] -ne '') {
        $Lines.Add('')
    }
    $Lines.Add("[$Section]")
    $Lines.Add("$Key = $literal")
}

function Prepare-IsolatedHdd {
    $sourceConfigPath = (Resolve-Path -LiteralPath $BaseConfig).Path
    Assert-BaseConfigPolicy $sourceConfigPath
    $seedPath = (Resolve-Path -LiteralPath $SeedHdd).Path
    $privatePath = [System.IO.Path]::GetFullPath($privateHdd)
    $runPath = [System.IO.Path]::GetFullPath($runDir).TrimEnd('\') + '\'
    if (-not $privatePath.StartsWith($runPath, [StringComparison]::OrdinalIgnoreCase) -or
        [StringComparer]::OrdinalIgnoreCase.Equals($seedPath, $privatePath)) {
        throw 'Private HDD must be a unique child of the run directory and differ from the seed.'
    }
    $hddLifecycle.seed_path = $seedPath
    $hddLifecycle.private_path = $privatePath
    $hddLifecycle.seed_sha256_before = Get-Sha256 $seedPath
    $hddLifecycle.base_config_path = $sourceConfigPath
    $hddLifecycle.base_config_sha256 = Get-Sha256 $sourceConfigPath
    Copy-Item -LiteralPath $seedPath -Destination $privatePath
    # Copy-Item preserves a seed's read-only attribute. The seed stays immutable,
    # while the run-owned clone must be writable for xemu and snapshot restore.
    if ((Get-Item -LiteralPath $privatePath).IsReadOnly) {
        Set-ItemProperty -LiteralPath $privatePath -Name IsReadOnly -Value $false
    }
    $hddLifecycle.initial_private_sha256 = Get-Sha256 $privatePath
    $hddLifecycle.seed_sha256_after_clone = Get-Sha256 $seedPath
    if ($hddLifecycle.seed_sha256_before -ne $hddLifecycle.seed_sha256_after_clone) {
        throw 'The immutable HDD seed changed while it was being cloned.'
    }
    if ($hddLifecycle.initial_private_sha256 -ne $hddLifecycle.seed_sha256_before) {
        throw 'The private HDD clone does not match the immutable seed.'
    }
    $hddLifecycle.clone_status = 'complete'
    if ($LaunchMode -eq 'Snapshot') {
        Assert-SnapshotPresent $privatePath $Snapshot
        $hddLifecycle.snapshot = $Snapshot
        $hddLifecycle.snapshot_verified = $true
    } else {
        $hddLifecycle.snapshot = $null
        $hddLifecycle.snapshot_verified = $null
    }
    Copy-Item -LiteralPath $sourceConfigPath -Destination $configPath
    $configLines = [System.Collections.Generic.List[string]]::new()
    $configLines.AddRange([string[]][System.IO.File]::ReadAllLines($configPath))
    Set-ConfigValue $configLines 'hdd_path' $privatePath
    Set-RendererValue $configLines $Renderer
    Set-TomlBoolean $configLines 'perf' 'cache_shaders' ($ShaderCache -eq 'Enabled')
    Set-TomlBoolean $configLines 'tweaks' 'vk_hybrid_ubershaders' ($HybridUbershaders -eq 'On')
    if ($Disc) {
        Set-ConfigValue $configLines 'dvd_path' $Disc
    }
    [System.IO.File]::WriteAllLines(
        $configPath,
        $configLines,
        [System.Text.UTF8Encoding]::new($false)
    )
    $hddLifecycle.config_path = $configPath
    $hddLifecycle.config_hdd_path = $privatePath
    $hddLifecycle.launch_config_sha256 = Get-Sha256 $configPath
    $hddLifecycle.config_status = 'complete'
    $hddLifecycle.policy_validated = $true
    $hddLifecycle.renderer = $Renderer
    Write-HddLifecycle
}

function Get-MonotonicMicroseconds {
    # xemu's Windows g_get_monotonic_time() and Stopwatch are both backed by
    # QueryPerformanceCounter. Use the same clock so buffered log visibility
    # cannot move the measured frame boundary by a flush interval.
    return [int64][Math]::Floor(
        [Diagnostics.Stopwatch]::GetTimestamp() * 1000000.0 /
        [Diagnostics.Stopwatch]::Frequency
    )
}

function Get-RequiredProperty($Object, [string]$Name, [string]$Context) {
    $property = $Object.PSObject.Properties[$Name]
    if (-not $property -or $null -eq $property.Value -or
        [string]::IsNullOrWhiteSpace([string]$property.Value)) {
        throw "Build manifest is missing ${Context}.${Name}."
    }
    return $property.Value
}

$manifest = $null
$sourceOwnershipValid = $false
if ($RequireSourceOwnership -and -not $RequirePdb) {
    throw '-RequireSourceOwnership also requires -RequirePdb.'
}
if ($RequireSourceOwnership -and -not $BuildManifest) {
    throw '-RequireSourceOwnership requires -BuildManifest.'
}
if ($BuildManifest) {
    if (-not (Test-Path -LiteralPath $BuildManifest -PathType Leaf)) {
        throw "Build manifest was not found: $BuildManifest"
    }
    $manifest = Get-Content -LiteralPath $BuildManifest -Raw | ConvertFrom-Json
    if ([int](Get-RequiredProperty $manifest 'schema_version' 'root') -ne 1) {
        throw 'Only xemu build identity schema version 1 is supported.'
    }
    $sourceCommit = [string](Get-RequiredProperty $manifest 'source_commit' 'root')
    if ($sourceCommit -notmatch '^[0-9a-fA-F]{40}$') {
        throw 'Build manifest source_commit must be a full 40-character Git SHA.'
    }
    $compiler = Get-RequiredProperty $manifest 'compiler' 'root'
    [void](Get-RequiredProperty $compiler 'name' 'compiler')
    [void](Get-RequiredProperty $compiler 'version' 'compiler')
    [void](Get-RequiredProperty $manifest 'lto_state' 'root')
    $artifacts = Get-RequiredProperty $manifest 'artifacts' 'root'
    foreach ($role in @('executable', 'pdb', 'dwarf_executable', 'map')) {
        $artifact = Get-RequiredProperty $artifacts $role 'artifacts'
        $hash = [string](Get-RequiredProperty $artifact 'sha256' "artifacts.${role}")
        if ($hash -notmatch '^[0-9a-fA-F]{64}$') {
            throw "Build manifest artifacts.${role}.sha256 is not SHA-256."
        }
    }
    $actualXemuHash = Get-Sha256 $Xemu
    if ($actualXemuHash -ne [string]$artifacts.executable.sha256) {
        throw 'Selected xemu.exe does not match the build manifest.'
    }
    if (Test-Path -LiteralPath $pdb -PathType Leaf) {
        $actualPdbHash = Get-Sha256 $pdb
        if ($actualPdbHash -ne [string]$artifacts.pdb.sha256) {
            throw 'Selected xemu.pdb does not match the build manifest.'
        }
    } elseif ($RequireSourceOwnership) {
        throw "Source ownership requires the manifest PDB beside xemu.exe: $pdb"
    }
    $sourceOwnershipValid = $pdbMatchVerified
    $manifest | ConvertTo-Json -Depth 8 |
        Set-Content -LiteralPath $buildIdentity -Encoding utf8
}

function Invoke-Wpr([string[]]$Arguments) {
    $stdout = [System.IO.Path]::GetTempFileName()
    $stderr = [System.IO.Path]::GetTempFileName()
    try {
        # WPR writes normal progress to stderr. Keep native output away from the
        # PowerShell error stream and judge the command only by its exit code.
        $process = Start-Process -FilePath $Wpr `
            -ArgumentList $Arguments `
            -WindowStyle Hidden `
            -Wait `
            -PassThru `
            -RedirectStandardOutput $stdout `
            -RedirectStandardError $stderr
        $output = @(
            (Get-Content -LiteralPath $stdout -Raw -ErrorAction SilentlyContinue)
            (Get-Content -LiteralPath $stderr -Raw -ErrorAction SilentlyContinue)
        ) -join "`n"
        $exitCode = $process.ExitCode
    } finally {
        Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue
    }
    if ($exitCode -ne 0) {
        throw "wpr.exe $($Arguments -join ' ') failed with exit code ${exitCode}: $output"
    }
    return $output
}

function Write-TraceMarker([string]$Name) {
    if ($captureStarted) {
        Invoke-Wpr @('-marker', $Name) | Out-Null
    }
}

function Get-Percentile([double[]]$Values, [double]$Percentile) {
    if ($Values.Count -eq 0) {
        return $null
    }
    $ordered = @($Values | Sort-Object)
    $rank = [Math]::Ceiling(($Percentile / 100.0) * $ordered.Count) - 1
    $rank = [Math]::Max(0, [Math]::Min($rank, $ordered.Count - 1))
    return [double]$ordered[$rank]
}

function Get-TraceLoss([string]$EtlPath) {
    $stdout = [System.IO.Path]::GetTempFileName()
    $stderr = [System.IO.Path]::GetTempFileName()
    $process = $null
    $text = ''
    try {
        $process = Start-Process -FilePath $Xperf `
            -ArgumentList @('-i', $EtlPath, '-a', 'tracestats') `
            -WindowStyle Hidden -Wait -PassThru `
            -RedirectStandardOutput $stdout `
            -RedirectStandardError $stderr
        $text = @(
            (Get-Content -LiteralPath $stdout -Raw -ErrorAction SilentlyContinue)
            (Get-Content -LiteralPath $stderr -Raw -ErrorAction SilentlyContinue)
        ) -join "`n"
    } finally {
        Remove-Item -LiteralPath $stdout, $stderr -Force `
            -ErrorAction SilentlyContinue
    }
    $text | Set-Content -LiteralPath $traceStats -Encoding utf8
    if (-not $process) {
        throw 'xperf tracestats did not start.'
    }
    if ($process.ExitCode -ne 0) {
        throw "xperf tracestats failed with exit code $($process.ExitCode)"
    }
    $lostEvents = [regex]::Match(
        $text, 'Total # Lost Events\s*:\s*(\d+)'
    )
    $lostBuffers = [regex]::Match(
        $text, 'Total # Lost Buffers\s*:\s*(\d+)'
    )
    if (-not $lostEvents.Success -or -not $lostBuffers.Success) {
        throw 'xperf tracestats did not report total lost events and buffers.'
    }
    return [pscustomobject]@{
        events = [uint64]$lostEvents.Groups[1].Value
        buffers = [uint64]$lostBuffers.Groups[1].Value
    }
}

function Get-WprStartArguments {
    switch ($TraceProfile) {
        'CpuScheduler' {
            return @('-start', 'GeneralProfile.Verbose', '-filemode')
        }
        'Gpu' {
            return @('-start', 'GPU.Verbose', '-filemode')
        }
        'Syscalls' {
            return @('-start', ($SyscallWprp + '!XemuSyscalls'), '-filemode')
        }
    }
}

function Save-LaunchLogs($Launch) {
    if (-not $Launch) {
        return
    }
    if ($Launch.Stdout -and (Test-Path -LiteralPath $Launch.Stdout)) {
        Copy-Item -LiteralPath $Launch.Stdout -Destination $launchStdout -Force
    }
    if ($Launch.Stderr -and (Test-Path -LiteralPath $Launch.Stderr)) {
        Copy-Item -LiteralPath $Launch.Stderr -Destination $launchStderr -Force
    }
}

$hddLifecycle = [ordered]@{
    schema_version = 1
    workload = $Game
    run_id = $RunId
    seed_path = $null
    seed_sha256_before = $null
    seed_sha256_after_clone = $null
    seed_sha256_final = $null
    base_config_path = $null
    base_config_sha256 = $null
    private_path = $privateHdd
    initial_private_sha256 = $null
    final_private_sha256 = $null
    snapshot = if ($LaunchMode -eq 'Snapshot') { $Snapshot } else { $null }
    snapshot_verified = $false
    clone_status = 'not_started'
    config_path = $configPath
    config_hdd_path = $null
    launch_config_sha256 = $null
    policy_validated = $false
    renderer = $Renderer
    shader_cache = $ShaderCache
    hybrid_ubershaders = $HybridUbershaders
    config_status = 'not_started'
    cleanup_status = 'not_started'
    cleanup_error = $null
    recorded_utc = $null
}
$captureStarted = $false
$nvidiaProcess = $null
$presentMonProcess = $null
$xemuProcess = $null
$launch = $null
$savedSymbolPath = [Environment]::GetEnvironmentVariable(
    '_NT_SYMBOL_PATH', 'Process'
)
$effectiveSymbolPath = $null
try {
    Prepare-IsolatedHdd
    $effectiveSymbolPath = if ($SymbolPath) {
        $SymbolPath
    } else {
        $buildDirectory + ';srv*C:\xemu-lab\symbols*https://msdl.microsoft.com/download/symbols'
    }
    [Environment]::SetEnvironmentVariable(
        '_NT_SYMBOL_PATH', $effectiveSymbolPath, 'Process'
    )

    if ($TraceProfile -ne 'None' -and $effectiveTraceStartMode -eq 'Startup') {
        Invoke-Wpr (Get-WprStartArguments) | Out-Null
        $captureStarted = $true
    }
    Write-TraceMarker 'xemu.startup.begin'

    $launch = & (Join-Path $suiteRoot 'start-retail-snapshot.ps1') `
        -Xemu $Xemu -ConfigPath $configPath `
        -LaunchMode $LaunchMode -Snapshot $Snapshot `
        -FlipLog $flipLog -GuestTraceLog $guestTraceLog `
        -FrameLog $frameLog -EventLog $eventLog -Disc $disc `
        -VkPerfLog $(if ($vkTelemetryActive) { $vkPerfLog } else { '' }) `
        -Renderer $Renderer -SurfaceScale $SurfaceScale `
        -VertexStagingInitialMiB $VertexStagingInitialMiB `
        -ReuseIdenticalIndexPayloads $ReuseIdenticalIndexPayloads `
        -ExpandDescriptorSets $ExpandDescriptorSets `
        -TlbDirtyHostPageFilter $TlbDirtyHostPageFilter `
        -SkipEquivalentTextureScaleUpdates $SkipEquivalentTextureScaleUpdates `
        -ProfileRoot $ProfileRoot
    if (-not $launch.IsolatedProfileExplicit -or -not $launch.ProfileActivationReceipt) {
        throw 'The private launcher did not explicitly apply the isolated profile.'
    }
    $xemuProcess = Get-Process -Id $launch.ProcessId -ErrorAction SilentlyContinue
    if (-not $xemuProcess) {
        Save-LaunchLogs $launch
        $launchError = Get-Content -LiteralPath $launch.Stderr -Raw `
            -ErrorAction SilentlyContinue
        throw "xemu exited during ${LaunchMode} startup: $launchError"
    }
    $hddLifecycle.launch_config_sha256 = Get-Sha256 $configPath
    Write-HddLifecycle
    Write-TraceMarker "xemu.startup.pid.$($xemuProcess.Id)"
    Write-TraceMarker 'xemu.game_load.begin'

    if ($LaunchMode -eq 'FreshBoot') {
        & (Join-Path $suiteRoot 'invoke-xemu-timed-key-sequence.ps1') `
            -ProcessId $xemuProcess.Id `
            -BiosDelaySeconds $FreshBootBiosDelaySeconds `
            -KeySequence $FreshBootKeySequence `
            -OutputPath $freshBootInputLog | Out-Null
    } else {
        if ($SnapshotKeySequence.Count -gt 0) {
            & (Join-Path $suiteRoot 'invoke-xemu-timed-key-sequence.ps1') `
                -ProcessId $xemuProcess.Id `
                -BiosDelaySeconds 0 `
                -KeySequence $SnapshotKeySequence `
                -OutputPath $freshBootInputLog | Out-Null
        } else {
            Start-Sleep -Seconds 7
            $xemuProcess.Refresh()
            if ($xemuProcess.HasExited) {
                $launchError = Get-Content -LiteralPath $launch.Stderr -Raw `
                    -ErrorAction SilentlyContinue
                throw "xemu exited before controller resume: $launchError"
            }
            & (Join-Path $suiteRoot 'send-xemu-key.ps1') `
                -ProcessId $xemuProcess.Id -VirtualKey 13
            Start-Sleep -Seconds $ResumeDelaySeconds
            for ($resumeKeyIndex = 0; $resumeKeyIndex -lt $ResumeKeyCount;
                 $resumeKeyIndex++) {
                & (Join-Path $suiteRoot 'send-xemu-key.ps1') `
                    -ProcessId $xemuProcess.Id -VirtualKey $ResumeVirtualKey
                if ($resumeKeyIndex + 1 -lt $ResumeKeyCount) {
                    Start-Sleep -Milliseconds 500
                }
            }
        }
    }
    Write-TraceMarker 'xemu.game_load.end'
    Write-TraceMarker 'xemu.warmup.begin'
    if ($WarmupSeconds -gt 0) {
        Start-Sleep -Seconds $WarmupSeconds
    }
    Write-TraceMarker 'xemu.warmup.end'

    $xemuProcess.Refresh()
    if ($xemuProcess.HasExited) {
        throw "xemu exited before capture with code $($xemuProcess.ExitCode)"
    }
    [void][Pgr2WprWindow]::SetForegroundWindow($xemuProcess.MainWindowHandle)
    & $ScreenshotTool -OutputPath $screenshot
    Save-LaunchLogs $launch

    $xemuHash = Get-Sha256 $Xemu
    Copy-Item -LiteralPath $configPath -Destination $configCopy -Force
    $configHash = Get-Sha256 $configCopy
    @(
        "MODE=$Mode"
        "RUN_ID=$RunId"
        "LAUNCH_MODE=$LaunchMode"
        "SNAPSHOT=$(if ($LaunchMode -eq 'Snapshot') { $Snapshot } else { 'NONE' })"
        "FRESH_BOOT_BIOS_DELAY_SECONDS=$(if ($LaunchMode -eq 'FreshBoot') { $FreshBootBiosDelaySeconds } else { 'NONE' })"
        "FRESH_BOOT_KEY_SEQUENCE=$(if ($LaunchMode -eq 'FreshBoot') { $FreshBootKeySequence -join ',' } else { 'NONE' })"
        "FRESH_BOOT_INPUT_LOG=$(if ($LaunchMode -eq 'FreshBoot') { $freshBootInputLog } else { 'NONE' })"
        "TRACE_PROFILE=$TraceProfile"
        "TRACE_START_MODE=$effectiveTraceStartMode"
        "PRESENTMON_MODE=$PresentMonMode"
        "RENDERER=$Renderer"
        "SURFACE_SCALE=$SurfaceScale"
        "VERTEX_STAGING_INITIAL_MIB=$VertexStagingInitialMiB"
        "REUSE_IDENTICAL_INDEX_PAYLOADS=$ReuseIdenticalIndexPayloads"
        "EXPAND_DESCRIPTOR_SETS=$ExpandDescriptorSets"
        "TLB_DIRTY_HOST_PAGE_FILTER=$TlbDirtyHostPageFilter"
        "SKIP_EQUIVALENT_TEXTURE_SCALE_UPDATES=$SkipEquivalentTextureScaleUpdates"
        "WARMUP_SECONDS=$WarmupSeconds"
        "DURATION_SECONDS=$DurationSeconds"
        "RESUME_VIRTUAL_KEY=$ResumeVirtualKey"
        "RESUME_DELAY_SECONDS=$ResumeDelaySeconds"
        "SNAPSHOT_KEY_SEQUENCE=$($SnapshotKeySequence -join ',')"
        "XEMU_PID=$($xemuProcess.Id)"
        "XEMU_PATH=$Xemu"
        "XEMU_SHA256=$xemuHash"
        "BUILD_MANIFEST=$BuildManifest"
        "BUILD_IDENTITY=$buildIdentity"
        "SOURCE_OWNERSHIP_VALID=$sourceOwnershipValid"
        "XEMU_CONFIG=$configCopy"
        "XEMU_CONFIG_SHA256=$configHash"
        "HDD_SEED=$($hddLifecycle.seed_path)"
        "HDD_SEED_SHA256=$($hddLifecycle.seed_sha256_before)"
        "HDD_PRIVATE=$($hddLifecycle.private_path)"
        "HDD_PRIVATE_INITIAL_SHA256=$($hddLifecycle.initial_private_sha256)"
        "BASE_CONFIG=$($hddLifecycle.base_config_path)"
        "BASE_CONFIG_SHA256=$($hddLifecycle.base_config_sha256)"
        "LAUNCH_CONFIG_SHA256=$($hddLifecycle.launch_config_sha256)"
        "CONFIG_POLICY_VALIDATED=$($hddLifecycle.policy_validated)"
        "CONFIG_RENDERER=$($hddLifecycle.renderer)"
        "HDD_LIFECYCLE=$hddLifecyclePath"
        "DISC=$disc"
        "CAPTURE_STARTED_AT=$((Get-Date).ToUniversalTime().ToString('o'))"
        "ETL=$etl"
        "GPU_CSV=$gpuCsv"
        "FLIP_LOG=$flipLog"
        "FRAME_LOG=$frameLog"
        "FRAME_LOG_MEASURED=$frameLogMeasured"
        "EVENT_LOG=$eventLog"
        "VK_TELEMETRY=$VkTelemetry"
        "VK_TELEMETRY_ACTIVE=$vkTelemetryActive"
        "VK_PERF_LOG=$vkPerfLog"
        "PRESENTMON_CSV=$(if ($PresentMonMode -eq 'Enabled') { $presentMonCsv } else { 'NONE' })"
        "SCREENSHOT=$screenshot"
        "PDB=$pdb"
        "PDB_PRESENT=$(Test-Path -LiteralPath $pdb -PathType Leaf)"
        "PDB_MATCH_VERIFIED=$pdbMatchVerified"
        "SYMBOL_PREFLIGHT=$symbolPreflight"
        "DUMPBIN=$resolvedDumpbin"
        "SYMBOL_PATH=$effectiveSymbolPath"
    ) | Set-Content -LiteralPath $runInfo -Encoding utf8

    if (Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue) {
        $query = 'timestamp,pstate,utilization.gpu,utilization.memory,memory.used,clocks.current.graphics,clocks.current.memory,power.draw,temperature.gpu'
        $nvidiaProcess = Start-Process -FilePath 'nvidia-smi.exe' -ArgumentList @(
            "--query-gpu=$query",
            '--format=csv,noheader,nounits',
            '--loop-ms=500',
            "--filename=$gpuCsv"
        ) -WindowStyle Hidden -PassThru
    }

    # XEMU_FLIP_LOG is the guest-frame contract. PresentMon sees the host
    # presentation path, which can continue at 60 Hz while a 30 Hz game
    # repeats frames. Remember the current completed-window count so startup
    # and controller-resume activity is excluded.
    $flipLineStart = 0
    if (Test-Path -LiteralPath $flipLog -PathType Leaf) {
        $flipLineStart = @(Get-Content -LiteralPath $flipLog).Count
    }
    $guestTraceLineStart = 0
    if (Test-Path -LiteralPath $guestTraceLog -PathType Leaf) {
        $guestTraceLineStart = @(Get-Content -LiteralPath $guestTraceLog).Count
    }
    $frameLineStart = 0
    if (Test-Path -LiteralPath $frameLog -PathType Leaf) {
        $frameLineStart = @(Get-Content -LiteralPath $frameLog).Count
    }
    $eventLineCursor = 0
    if (Test-Path -LiteralPath $eventLog -PathType Leaf) {
        $eventLineCursor = @(Get-Content -LiteralPath $eventLog).Count
    }
    $frameLineCursor = $frameLineStart
    $lastStallMarkerUtc = [DateTime]::MinValue
    $markedEventClasses = @{}

    if ($TraceProfile -ne 'None' -and -not $captureStarted) {
        Invoke-Wpr (Get-WprStartArguments) | Out-Null
        $captureStarted = $true
    }
    $steadyStartMonotonicUs = Get-MonotonicMicroseconds
    $steadyStartUtc = [DateTime]::UtcNow
    Write-TraceMarker 'xemu.steady_state.begin'
    @(
        "STEADY_STATE_START_MONOTONIC_US=$steadyStartMonotonicUs"
        'GUEST_FRAME_BOUNDARY=complete frames selected by QPC timestamp'
    ) | Add-Content -LiteralPath $runInfo -Encoding utf8

    if ($PresentMonMode -eq 'Enabled') {
        $presentMonProcess = Start-Process -FilePath $PresentMon -ArgumentList @(
            '--process_id', $xemuProcess.Id,
            '--output_file', $presentMonCsv,
            '--timed', $DurationSeconds,
            '--terminate_after_timed',
            '--no_console_stats',
            '--v1_metrics',
            '--session_name', ('XemuLab-' + $RunId)
        ) -WindowStyle Hidden -PassThru `
          -RedirectStandardOutput $presentMonStdout `
          -RedirectStandardError $presentMonStderr
    }

    $focusLoss = 0
    $notResponding = 0
    $deadlineMonotonicUs = $steadyStartMonotonicUs +
        ([int64]$DurationSeconds * 1000000)
    while ($true) {
        $remainingUs = $deadlineMonotonicUs - (Get-MonotonicMicroseconds)
        if ($remainingUs -le 0) {
            break
        }
        $pollMilliseconds = [Math]::Min(
            500, [Math]::Max(1, [Math]::Ceiling($remainingUs / 1000.0))
        )
        Start-Sleep -Milliseconds $pollMilliseconds
        $xemuProcess.Refresh()
        if ($xemuProcess.HasExited) {
            throw "xemu exited during capture with code $($xemuProcess.ExitCode)"
        }
        if (-not $xemuProcess.Responding) {
            $notResponding++
        }
        if ([Pgr2WprWindow]::GetForegroundWindow() -ne $xemuProcess.MainWindowHandle) {
            $focusLoss++
            [void][Pgr2WprWindow]::SetForegroundWindow($xemuProcess.MainWindowHandle)
        }

        if (Test-Path -LiteralPath $frameLog -PathType Leaf) {
            $frameLines = @(Get-Content -LiteralPath $frameLog)
            foreach ($line in @($frameLines | Select-Object -Skip $frameLineCursor)) {
                if ($line -match 'delta_us=(\d+)') {
                    $deltaUs = [uint64]$Matches[1]
                    if ($deltaUs -ge ([uint64]$FrameStallMilliseconds * 1000) -and
                        ([DateTime]::UtcNow - $lastStallMarkerUtc).TotalSeconds -ge 1) {
                        Write-TraceMarker "xemu.frame_stall.us.${deltaUs}"
                        $lastStallMarkerUtc = [DateTime]::UtcNow
                    }
                }
            }
            $frameLineCursor = $frameLines.Count
        }

        if (Test-Path -LiteralPath $eventLog -PathType Leaf) {
            $eventLines = @(Get-Content -LiteralPath $eventLog)
            foreach ($line in @($eventLines | Select-Object -Skip $eventLineCursor)) {
                try {
                    $event = $line | ConvertFrom-Json
                    $eventClass = [string]$event.event
                    if ($eventClass -in @(
                            'shader_compile', 'gpu_submit', 'readback'
                        ) -and -not $markedEventClasses.ContainsKey($eventClass)) {
                        Write-TraceMarker "xemu.${eventClass}.first"
                        $markedEventClasses[$eventClass] = $true
                    }
                } catch {
                    # Ignore an incomplete final JSONL line while xemu writes it.
                }
            }
            $eventLineCursor = $eventLines.Count
        }
    }

    $steadyEndMonotonicUs = Get-MonotonicMicroseconds
    $steadyEndUtc = [DateTime]::UtcNow
    # Freeze the QPC boundary and non-timestamped aggregate flip windows before
    # WPR rundown. Timestamped frame records are selected against this exact
    # boundary after the buffers become visible.
    $flipLinesAtDeadline = @()
    if (Test-Path -LiteralPath $flipLog -PathType Leaf) {
        $allFlipLines = @(Get-Content -LiteralPath $flipLog)
        if ($allFlipLines.Count -gt $flipLineStart) {
            $flipLinesAtDeadline = @(
                $allFlipLines | Select-Object -Skip $flipLineStart
            )
        }
    }
    $guestTraceLinesAtDeadline = @()
    if (Test-Path -LiteralPath $guestTraceLog -PathType Leaf) {
        $allGuestTraceLines = @(Get-Content -LiteralPath $guestTraceLog)
        if ($allGuestTraceLines.Count -gt $guestTraceLineStart) {
            $guestTraceLinesAtDeadline = @(
                $allGuestTraceLines | Select-Object -Skip $guestTraceLineStart
            )
        }
    }
    Write-TraceMarker 'xemu.steady_state.end'
    if ($captureStarted) {
        Invoke-Wpr @('-stop', $etl) | Out-Null
        $captureStarted = $false
    }
    # The telemetry streams are intentionally buffered. The measured boundary
    # comes from QPC timestamps, so waiting outside the trace only makes the
    # final measured records visible and cannot extend the selected interval.
    Start-Sleep -Milliseconds 1100

    $presentRows = @()
    $meanHostPresentMs = $null
    $hostPresentFps = $null
    [double[]]$hostFrameTimesMs = @()
    $hostP95Ms = $null
    $hostP99Ms = $null
    $hostMaxMs = $null
    $hostWorstIntervalsMs = @()
    if ($PresentMonMode -eq 'Enabled') {
        if (-not $presentMonProcess.WaitForExit(10000)) {
            throw 'PresentMon did not stop after the timed capture.'
        }
        if ($presentMonProcess.ExitCode -ne 0) {
            $presentMonError = Get-Content -LiteralPath $presentMonStderr `
                -Raw -ErrorAction SilentlyContinue
            throw "PresentMon failed with exit code $($presentMonProcess.ExitCode): $presentMonError"
        }
        if (-not (Test-Path -LiteralPath $presentMonCsv -PathType Leaf)) {
            throw "PresentMon emitted no output CSV: $presentMonCsv"
        }
        $presentRows = @(Import-Csv -LiteralPath $presentMonCsv | Where-Object {
            $_.msBetweenPresents -and [double]$_.msBetweenPresents -gt 0
        })
        if ($presentRows.Count -lt 2) {
            throw "PresentMon returned only $($presentRows.Count) usable frames."
        }
        $meanHostPresentMs = (
            $presentRows |
                Measure-Object -Property msBetweenPresents -Average
        ).Average
        $hostPresentFps = 1000.0 / [double]$meanHostPresentMs
        $hostFrameTimesMs = @(
            $presentRows | ForEach-Object { [double]$_.msBetweenPresents }
        )
        $hostP95Ms = Get-Percentile $hostFrameTimesMs 95
        $hostP99Ms = Get-Percentile $hostFrameTimesMs 99
        $hostMaxMs = ($hostFrameTimesMs | Measure-Object -Maximum).Maximum
        $hostWorstIntervalsMs = @($hostFrameTimesMs | Sort-Object -Descending | Select-Object -First 10)
    }

    [double[]]$guestFrameTimesMs = @()
    $measuredFrameLines = New-Object System.Collections.Generic.List[string]
    $measuredFrameIds = New-Object 'System.Collections.Generic.HashSet[uint64]'
    if (Test-Path -LiteralPath $frameLog -PathType Leaf) {
        $frameLogLines = @(Get-Content -LiteralPath $frameLog)
        foreach ($line in $frameLogLines) {
            if ($line -notmatch
                '^timestamp_us=(\d+) frame=(\d+) delta_us=(\d+)') {
                continue
            }
            $timestampUs = [int64]$Matches[1]
            $frameId = [uint64]$Matches[2]
            $deltaUs = [int64]$Matches[3]
            $frameStartUs = $timestampUs - $deltaUs
            if ($frameStartUs -lt $steadyStartMonotonicUs -or
                $timestampUs -gt $steadyEndMonotonicUs) {
                continue
            }
            $measuredFrameLines.Add($line)
            [void]$measuredFrameIds.Add($frameId)
            $guestFrameTimesMs += [double]$deltaUs / 1000.0
        }
    }
    $measuredFrameLines |
        Set-Content -LiteralPath $frameLogMeasured -Encoding utf8
    $guestTraceTimestamps = @()
    if ($guestFrameTimesMs.Count -eq 0) {
        foreach ($line in $guestTraceLinesAtDeadline) {
            if ($line -match '^\s*(\d{4}-\d{2}-\d{2}T[^\s]+)\s+nv2a_pgraph_flip_increment_write') {
                $guestTraceTimestamps += [DateTime]::Parse($Matches[1]).ToUniversalTime()
            } elseif ($line -match '^\s*\[?(\d+(?:\.\d+)?)\]?\s+nv2a_pgraph_flip_increment_write') {
                $guestTraceTimestamps += [double]$Matches[1]
            }
        }
        if ($guestTraceTimestamps.Count -ge 2) {
            for ($index = 1; $index -lt $guestTraceTimestamps.Count; $index++) {
                if ($guestTraceTimestamps[$index] -is [DateTime]) {
                    $guestFrameTimesMs += ($guestTraceTimestamps[$index] - $guestTraceTimestamps[$index - 1]).TotalMilliseconds
                } else {
                    $guestFrameTimesMs += (($guestTraceTimestamps[$index] - $guestTraceTimestamps[$index - 1]) * 1000.0)
                }
            }
        }
    }
    $guestFrameAverageMs = $null
    $guestFrameP95Ms = $null
    $guestFrameP99Ms = $null
    $guestFrameMaxMs = $null
    $guestWorstIntervalsMs = @()
    $guestStallCount = 0
    if ($guestFrameTimesMs.Count -gt 0) {
        $guestFrameAverageMs = (
            $guestFrameTimesMs | Measure-Object -Average
        ).Average
        $guestFrameP95Ms = Get-Percentile $guestFrameTimesMs 95
        $guestFrameP99Ms = Get-Percentile $guestFrameTimesMs 99
        $guestFrameMaxMs = ($guestFrameTimesMs | Measure-Object -Maximum).Maximum
        $guestWorstIntervalsMs = @($guestFrameTimesMs | Sort-Object -Descending | Select-Object -First 10)
        $guestStallCount = @($guestFrameTimesMs | Where-Object {
            $_ -ge $FrameStallMilliseconds
        }).Count
    }

    $loss = if ($TraceProfile -eq 'None') {
        [pscustomobject]@{ events = [uint64]0; buffers = [uint64]0 }
    } else {
        Get-TraceLoss $etl
    }
    if ($loss.events -ne 0 -or $loss.buffers -ne 0) {
        throw "ETW data loss: $($loss.events) events, $($loss.buffers) buffers. Increase the selected WPR profile buffer tier and rerun."
    }

    if ($vkTelemetryActive) {
        if (-not (Test-Path -LiteralPath $vkPerfLog -PathType Leaf)) {
            throw 'Vulkan telemetry was enabled but xemu did not create its log.'
        }
        $vkLines = @(Get-Content -LiteralPath $vkPerfLog)
        $measuredLines = New-Object System.Collections.Generic.List[string]
        $measuredVkFrameIds = New-Object `
            'System.Collections.Generic.HashSet[uint64]'
        if ($vkLines.Count -gt 0 -and $vkLines[0] -match '"type":"schema"') {
            $measuredLines.Add($vkLines[0])
        }
        foreach ($line in $vkLines) {
            if ($line -notmatch '"type":"frame"') {
                continue
            }
            try {
                $frameRecord = $line | ConvertFrom-Json
                if ($measuredFrameIds.Contains(
                        [uint64]$frameRecord.guest_frame)) {
                    $measuredLines.Add($line)
                    [void]$measuredVkFrameIds.Add(
                        [uint64]$frameRecord.guest_frame)
                }
            } catch {
                # Ignore an incomplete final JSONL line while xemu writes it.
            }
        }
        if ($measuredLines.Count -lt 2) {
            throw 'Vulkan telemetry contained no measured guest-frame records.'
        }
        if ($measuredVkFrameIds.Count -ne $measuredFrameIds.Count) {
            throw "Vulkan/frame-log boundary mismatch: $($measuredVkFrameIds.Count) Vulkan records for $($measuredFrameIds.Count) complete frames."
        }
        $measuredLines | Set-Content -LiteralPath $vkPerfMeasured -Encoding utf8
        & $python (Join-Path $suiteRoot 'summarize-vk-perf.py') `
            $vkPerfMeasured --output $vkPerfSummary | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw 'Vulkan telemetry summarization failed.'
        }
    }

    $frameSummary = [ordered]@{
        schema_version = 1
        guest_frame_source = if ($guestFrameTimesMs.Count -gt 0) {
            'XEMU_FRAME_LOG'
        } else {
            $null
        }
        guest_frame_count = $guestFrameTimesMs.Count
        guest_average_ms = $guestFrameAverageMs
        guest_p95_ms = $guestFrameP95Ms
        guest_p99_ms = $guestFrameP99Ms
        guest_max_ms = $guestFrameMaxMs
        guest_worst_intervals_ms = $guestWorstIntervalsMs
        guest_stall_threshold_ms = $FrameStallMilliseconds
        guest_stall_count = $guestStallCount
        host_present_source = if ($PresentMonMode -eq 'Enabled') {
            'PresentMon'
        } else {
            $null
        }
        host_present_count = $hostFrameTimesMs.Count
        host_present_average_ms = $meanHostPresentMs
        host_present_p95_ms = $hostP95Ms
        host_present_p99_ms = $hostP99Ms
        host_present_max_ms = $hostMaxMs
        host_present_worst_intervals_ms = $hostWorstIntervalsMs
    }
    $frameSummary | ConvertTo-Json -Depth 4 |
        Set-Content -LiteralPath $frameStats -Encoding utf8

    $filter = [ordered]@{
        schema_version = 1
        xemu_pid = $xemuProcess.Id
        xemu_path = $Xemu
        trace_profile = $TraceProfile
        trace_start_mode = $effectiveTraceStartMode
        renderer = $Renderer
        shader_cache = $ShaderCache
        hybrid_ubershaders = $HybridUbershaders
        surface_scale = $SurfaceScale
        vertex_staging_initial_mib = $VertexStagingInitialMiB
        reuse_identical_index_payloads = $ReuseIdenticalIndexPayloads
        expand_descriptor_sets = $ExpandDescriptorSets
        tlb_dirty_host_page_filter = $TlbDirtyHostPageFilter
        skip_equivalent_texture_scale_updates = $SkipEquivalentTextureScaleUpdates
        steady_state_start_utc = $steadyStartUtc.ToString('o')
        steady_state_end_utc = $steadyEndUtc.ToString('o')
        steady_state_start_monotonic_us = $steadyStartMonotonicUs
        steady_state_end_monotonic_us = $steadyEndMonotonicUs
        guest_frame_boundary = 'complete frames selected by QPC timestamp'
        wpa_time_markers = if ($TraceProfile -eq 'None') { @() } else { @('xemu.steady_state.begin', 'xemu.steady_state.end') }
        process_filter = 'xemu.exe'
        thread_filter = 'inspect Process/Thread Name and Thread ID under xemu.exe'
        gpu_filter = 'select contexts whose owning process is the recorded xemu PID'
        stack_filter = 'group by Stack, then exclude unresolved frames only after symbol audit'
        symbol_path = $effectiveSymbolPath
        pdb_path = if (Test-Path -LiteralPath $pdb -PathType Leaf) { $pdb } else { $null }
    }
    $filter | ConvertTo-Json -Depth 4 |
        Set-Content -LiteralPath $analysisFilter -Encoding utf8

    if ($WpaProfile -and $TraceProfile -ne 'None') {
        New-Item -ItemType Directory -Path $wpaExportDirectory -Force |
            Out-Null
        $export = Start-Process -FilePath $WpaExporter -ArgumentList @(
            '-i', $etl,
            '-profile', $WpaProfile,
            '-outputfolder', $wpaExportDirectory,
            '-prefix', ($profileSlug + '-'),
            '-outputformat', 'CSV'
        ) -WindowStyle Hidden -Wait -PassThru
        if ($export.ExitCode -ne 0) {
            throw "WPAExporter failed with exit code $($export.ExitCode)"
        }
    }

    # XEMU_FLIP_LOG may be block-buffered, so line count at steady-state start
    # is not a reliable boundary. Select the newest complete windows whose
    # combined duration fits inside the measured interval.
    $allGuestFlipSamples = @()
    if (Test-Path -LiteralPath $flipLog -PathType Leaf) {
        foreach ($line in $flipLinesAtDeadline) {
            if ($line -match '^elapsed_us=(\d+) frames=(\d+) fps=([0-9.]+)$') {
                $allGuestFlipSamples += [pscustomobject]@{
                    elapsed_us = [uint64]$Matches[1]
                    frames = [uint64]$Matches[2]
                    reported_fps = [double]$Matches[3]
                }
            }
        }
    }
    [object[]]$selectedNewest = @()
    $selectedElapsedUs = [uint64]0
    $maximumMeasuredUs = [uint64]$DurationSeconds * 1000000
    for ($index = $allGuestFlipSamples.Count - 1; $index -ge 0; $index--) {
        $sample = $allGuestFlipSamples[$index]
        if (($selectedElapsedUs + $sample.elapsed_us) -gt $maximumMeasuredUs) {
            break
        }
        $selectedNewest += $sample
        $selectedElapsedUs += $sample.elapsed_us
    }
    [object[]]$guestFlipSamples = $selectedNewest
    [array]::Reverse($guestFlipSamples)
    $guestFlipElapsedUs = [uint64]0
    $guestFlipFrames = [uint64]0
    foreach ($sample in $guestFlipSamples) {
        $guestFlipElapsedUs += $sample.elapsed_us
        $guestFlipFrames += $sample.frames
    }
    $guestAverageFps = $null
    $guestFpsSource = $null
    $measurementStatus = 'guest_flip_telemetry_missing'
    if ($guestFlipSamples.Count -gt 0 -and $guestFlipElapsedUs -gt 0) {
        $guestAverageFps = (
            [double]$guestFlipFrames * 1000000.0 /
            [double]$guestFlipElapsedUs
        )
        $guestFpsSource = 'XEMU_FLIP_LOG'
        $measurementStatus = 'complete'
    } elseif ($guestTraceTimestamps.Count -ge 2 -and $guestFrameAverageMs -gt 0) {
        $guestAverageFps = 1000.0 / [double]$guestFrameAverageMs
        $guestFlipFrames = [uint64]$guestTraceTimestamps.Count
        $guestFlipElapsedUs = [uint64][Math]::Round(
            ($guestFrameTimesMs | Measure-Object -Sum).Sum * 1000.0
        )
        $guestFpsSource = 'QEMU_TRACE_NV2A_DISPLAY_WRITE'
        $measurementStatus = 'complete'
    }

    @(
        "CAPTURE_COMPLETED_AT=$((Get-Date).ToUniversalTime().ToString('o'))"
        "STEADY_STATE_END_MONOTONIC_US=$steadyEndMonotonicUs"
        "FOCUS_LOSS_SAMPLES=$focusLoss"
        "NOT_RESPONDING_SAMPLES=$notResponding"
        ('PRESENTMON_HOST_FRAME_COUNT={0}' -f $presentRows.Count)
        ('HOST_PRESENT_AVERAGE_MS={0}' -f $(
            if ($null -eq $meanHostPresentMs) { 'UNAVAILABLE' }
            else { '{0:F6}' -f $meanHostPresentMs }
        ))
        ('HOST_PRESENT_AVERAGE_FPS={0}' -f $(
            if ($null -eq $hostPresentFps) { 'UNAVAILABLE' }
            else { '{0:F3}' -f $hostPresentFps }
        ))
        ('HOST_PRESENT_P95_MS={0}' -f $(
            if ($null -eq $hostP95Ms) { 'UNAVAILABLE' }
            else { '{0:F3}' -f $hostP95Ms }
        ))
        ('HOST_PRESENT_P99_MS={0}' -f $(
            if ($null -eq $hostP99Ms) { 'UNAVAILABLE' }
            else { '{0:F3}' -f $hostP99Ms }
        ))
        ('GUEST_FRAME_SAMPLE_COUNT={0}' -f $guestFrameTimesMs.Count)
        ('GUEST_FRAME_AVERAGE_MS={0}' -f $(
            if ($null -eq $guestFrameAverageMs) { 'UNAVAILABLE' }
            else { '{0:F3}' -f $guestFrameAverageMs }
        ))
        ('GUEST_FRAME_P95_MS={0}' -f $(
            if ($null -eq $guestFrameP95Ms) { 'UNAVAILABLE' }
            else { '{0:F3}' -f $guestFrameP95Ms }
        ))
        ('GUEST_FRAME_P99_MS={0}' -f $(
            if ($null -eq $guestFrameP99Ms) { 'UNAVAILABLE' }
            else { '{0:F3}' -f $guestFrameP99Ms }
        ))
        ('GUEST_FRAME_MAX_MS={0}' -f $(
            if ($null -eq $guestFrameMaxMs) { 'UNAVAILABLE' }
            else { '{0:F3}' -f $guestFrameMaxMs }
        ))
        "ETW_LOST_EVENTS=$($loss.events)"
        "ETW_LOST_BUFFERS=$($loss.buffers)"
        ('GUEST_FLIP_SAMPLE_COUNT={0}' -f $guestFlipSamples.Count)
        ('GUEST_FLIP_FRAME_COUNT={0}' -f $guestFlipFrames)
        ('GUEST_FLIP_ELAPSED_US={0}' -f $guestFlipElapsedUs)
        ('GUEST_FLIP_AVERAGE_FPS={0}' -f $(
            if ($null -eq $guestAverageFps) { 'UNAVAILABLE' }
            else { '{0:F3}' -f $guestAverageFps }
        ))
        "MEASUREMENT_STATUS=$measurementStatus"
    ) | Add-Content -LiteralPath $runInfo -Encoding utf8

    # PR71 publishes its bounded SPIR-V cache during renderer teardown.
    $gracefulShutdown = [ordered]@{
        schema_version = 1
        process_id = $xemuProcess.Id
        method = 'CloseMainWindow'
        requested = $false
        exited = $false
        exit_code = $null
        spirv_prewarm_summary_present = $false
        completed_utc = $null
    }
    $xemuProcess.Refresh()
    if ($xemuProcess.HasExited) {
        throw 'xemu exited before the required graceful renderer teardown.'
    }
    $gracefulShutdown.requested = [bool]$xemuProcess.CloseMainWindow()
    if (-not $gracefulShutdown.requested) {
        throw 'CloseMainWindow did not accept the graceful xemu shutdown request.'
    }
    if (-not $xemuProcess.WaitForExit(30000)) {
        throw 'xemu did not exit within 30 seconds of CloseMainWindow.'
    }
    $xemuProcess.Refresh()
    $gracefulShutdown.exited = $xemuProcess.HasExited
    $gracefulShutdown.exit_code = $xemuProcess.ExitCode
    Save-LaunchLogs $launch
    $spirvStderr = Get-Content -LiteralPath $launchStderr -Raw `
        -ErrorAction SilentlyContinue
    $gracefulShutdown.spirv_prewarm_summary_present =
        $spirvStderr -match '(?m)^nv2a/vk: SPIR-V prewarm '
    $gracefulShutdown.completed_utc = [DateTime]::UtcNow.ToString('o')
    $gracefulShutdown | ConvertTo-Json -Depth 4 |
        Set-Content -LiteralPath $gracefulShutdownPath -Encoding utf8
    if ($RequireSpirvSummary -and -not $gracefulShutdown.spirv_prewarm_summary_present) {
        throw 'Graceful renderer teardown emitted no SPIR-V prewarm summary.'
    }

    $result = [pscustomobject]@{
        status = if ($measurementStatus -eq 'complete') {
            'complete'
        } else {
            'incomplete'
        }
        functional_status = 'complete'
        measurement_status = $measurementStatus
        game = $Game
        run_id = $RunId
        launch_mode = $LaunchMode
        snapshot = if ($LaunchMode -eq 'Snapshot') { $Snapshot } else { $null }
        fresh_boot_bios_delay_seconds = if ($LaunchMode -eq 'FreshBoot') {
            $FreshBootBiosDelaySeconds
        } else {
            $null
        }
        fresh_boot_key_sequence = if ($LaunchMode -eq 'FreshBoot') {
            $FreshBootKeySequence
        } else {
            @()
        }
        fresh_boot_input_log = if ($LaunchMode -eq 'FreshBoot') {
            $freshBootInputLog
        } else {
            $null
        }
        snapshot_key_sequence = if ($LaunchMode -eq 'Snapshot') {
            $SnapshotKeySequence
        } else {
            @()
        }
        snapshot_input_log = if ($LaunchMode -eq 'Snapshot' -and $SnapshotKeySequence.Count -gt 0) {
            $freshBootInputLog
        } else {
            $null
        }
        duration_seconds = $DurationSeconds
        xemu = $Xemu
        xemu_sha256 = $xemuHash
        xemu_config = $configCopy
        xemu_config_sha256 = $configHash
        hdd_lifecycle = $hddLifecyclePath
        hdd_seed = $hddLifecycle.seed_path
        hdd_seed_sha256 = $hddLifecycle.seed_sha256_before
        hdd_private = $hddLifecycle.private_path
        hdd_private_initial_sha256 = $hddLifecycle.initial_private_sha256
        base_config = $hddLifecycle.base_config_path
        base_config_sha256 = $hddLifecycle.base_config_sha256
        launch_config_sha256 = $hddLifecycle.launch_config_sha256
        config_policy_validated = $hddLifecycle.policy_validated
        xemu_pid = $xemuProcess.Id
        focus_loss_samples = $focusLoss
        not_responding_samples = $notResponding
        evidence = $runDir
        graceful_shutdown = $gracefulShutdownPath
        profile_activation = $launch.ProfileActivationReceipt
        etl = if ($TraceProfile -eq 'None') { $null } else { $etl }
        trace_profile = $TraceProfile
        trace_start_mode = $effectiveTraceStartMode
        renderer = $Renderer
        surface_scale = $SurfaceScale
        vertex_staging_initial_mib = $VertexStagingInitialMiB
        reuse_identical_index_payloads = $ReuseIdenticalIndexPayloads
        expand_descriptor_sets = $ExpandDescriptorSets
        tlb_dirty_host_page_filter = $TlbDirtyHostPageFilter
        skip_equivalent_texture_scale_updates = $SkipEquivalentTextureScaleUpdates
        warmup_seconds = $WarmupSeconds
        steady_state_start_utc = $steadyStartUtc.ToString('o')
        steady_state_end_utc = $steadyEndUtc.ToString('o')
        steady_state_start_monotonic_us = $steadyStartMonotonicUs
        steady_state_end_monotonic_us = $steadyEndMonotonicUs
        guest_frame_boundary = 'complete frames selected by QPC timestamp'
        etw_lost_events = $loss.events
        etw_lost_buffers = $loss.buffers
        etw_collected = ($TraceProfile -ne 'None')
        trace_stats = if ($TraceProfile -eq 'None') { $null } else { $traceStats }
        analysis_filter = $analysisFilter
        frame_time_summary = $frameStats
        wpa_exports = if ($WpaProfile -and $TraceProfile -ne 'None') { $wpaExportDirectory } else { $null }
        symbol_path = $effectiveSymbolPath
        pdb = if (Test-Path -LiteralPath $pdb -PathType Leaf) { $pdb } else { $null }
        pdb_match_verified = $pdbMatchVerified
        build_manifest = if ($BuildManifest) { $buildIdentity } else { $null }
        source_ownership_valid = $sourceOwnershipValid
        symbol_preflight = if ($pdbMatchVerified) { $symbolPreflight } else { $null }
        gpu_csv = $gpuCsv
        flip_log = $flipLog
        guest_trace_log = $guestTraceLog
        frame_log = $frameLog
        frame_log_measured = $frameLogMeasured
        event_log = $eventLog
        vk_telemetry = $VkTelemetry
        vk_telemetry_active = $vkTelemetryActive
        vk_perf_log = if ($vkTelemetryActive) { $vkPerfLog } else { $null }
        vk_perf_measured = if ($vkTelemetryActive) { $vkPerfMeasured } else { $null }
        vk_perf_summary = if ($vkTelemetryActive) { $vkPerfSummary } else { $null }
        presentmon_mode = $PresentMonMode
        presentmon_csv = if ($PresentMonMode -eq 'Enabled') {
            $presentMonCsv
        } else {
            $null
        }
        screenshot = $screenshot
        launch_stdout = $launchStdout
        launch_stderr = $launchStderr
        presentmon_role = if ($PresentMonMode -eq 'Enabled') {
            'host_presentation_telemetry_only'
        } else {
            'disabled'
        }
        presentmon_frame_count = $presentRows.Count
        host_present_average_ms = $meanHostPresentMs
        host_present_average_fps = $hostPresentFps
        host_present_p95_ms = $hostP95Ms
        host_present_p99_ms = $hostP99Ms
        host_present_max_ms = $hostMaxMs
        host_present_worst_intervals_ms = $hostWorstIntervalsMs
        guest_frame_count = $guestFrameTimesMs.Count
        guest_frame_average_ms = $guestFrameAverageMs
        guest_frame_p95_ms = $guestFrameP95Ms
        guest_frame_p99_ms = $guestFrameP99Ms
        guest_frame_max_ms = $guestFrameMaxMs
        guest_frame_worst_intervals_ms = $guestWorstIntervalsMs
        guest_frame_stall_count = $guestStallCount
        fps_source = $guestFpsSource
        guest_flip_sample_count = $guestFlipSamples.Count
        guest_flip_frame_count = $guestFlipFrames
        guest_flip_elapsed_us = $guestFlipElapsedUs
        average_fps = $guestAverageFps
    }
    $result | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $completeMarker -Encoding utf8
    $result | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $buildResult -Encoding utf8
    $result
} catch {
    if ($captureStarted) {
        try {
            Invoke-Wpr @('-cancel') | Out-Null
        } catch {
            # Preserve the original capture failure.
        }
    }
    Save-LaunchLogs $launch
    $failure = [pscustomobject]@{
        status = 'failed'
        game = $Game
        run_id = $RunId
        launch_mode = $LaunchMode
        snapshot = if ($LaunchMode -eq 'Snapshot') { $Snapshot } else { $null }
        xemu = $Xemu
        launch_stdout = if (Test-Path -LiteralPath $launchStdout) {
            $launchStdout
        } else {
            $null
        }
        launch_stderr = if (Test-Path -LiteralPath $launchStderr) {
            $launchStderr
        } else {
            $null
        }
        evidence = $runDir
        hdd_lifecycle = $hddLifecyclePath
        error = $_.Exception.Message
    }
    $failure | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $completeMarker -Encoding utf8
    $failure | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $buildResult -Encoding utf8
    throw
} finally {
    [Environment]::SetEnvironmentVariable(
        '_NT_SYMBOL_PATH', $savedSymbolPath, 'Process'
    )
    if ($presentMonProcess -and -not $presentMonProcess.HasExited) {
        Stop-Process -Id $presentMonProcess.Id -Force -ErrorAction SilentlyContinue
    }
    if ($nvidiaProcess -and -not $nvidiaProcess.HasExited) {
        Stop-Process -Id $nvidiaProcess.Id -Force
        $nvidiaProcess.WaitForExit()
    }
    if ($xemuProcess -and -not $xemuProcess.HasExited) {
        Stop-Process -Id $xemuProcess.Id -Force
        try { [void]$xemuProcess.WaitForExit(30000) } catch { }
    }
    $cleanupFailure = $null
    try {
        if (Test-Path -LiteralPath $privateHdd -PathType Leaf) {
            Wait-HddExclusive $privateHdd
            $hddLifecycle.final_private_sha256 = Get-Sha256 $privateHdd
            $hddLifecycle.seed_sha256_final = Get-Sha256 $hddLifecycle.seed_path
            if ($hddLifecycle.seed_sha256_before -ne $hddLifecycle.seed_sha256_final) {
                throw 'The immutable HDD seed changed during the retail run.'
            }
            Remove-Item -LiteralPath $privateHdd -Force
            if (Test-Path -LiteralPath $privateHdd) {
                throw 'Private HDD remained after cleanup.'
            }
        }
        $hddLifecycle.cleanup_status = 'complete'
    } catch {
        $cleanupFailure = $_.Exception.Message
        $hddLifecycle.cleanup_status = 'failed'
        $hddLifecycle.cleanup_error = $cleanupFailure
    } finally {
        $hddLifecycle.recorded_utc = [DateTime]::UtcNow.ToString('o')
        try { Write-HddLifecycle } catch { }
    }
    if ($cleanupFailure) {
        throw "Retail HDD cleanup failed: $cleanupFailure"
    }
}
