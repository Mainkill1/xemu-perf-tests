param(
    [Parameter(Mandatory = $true)]
    [string]$Xemu,
    # A capture must pass a run-local configuration.  Keeping the optional
    # default preserves the standalone launcher for operator use, while the
    # capture wrappers always provide an isolated path.
    [string]$ConfigPath = '',
    [ValidateSet('Snapshot', 'FreshBoot')]
    [string]$LaunchMode = 'Snapshot',
    [string]$Snapshot = '6',
    [string]$FlipLog = '',
    # Standard QEMU trace fallback for official builds without XEMU_FLIP_LOG.
    [string]$GuestTraceLog = '',
    [string]$FrameLog = '',
    [string]$EventLog = '',
    [string]$VkPerfLog = '',
    [string]$Disc = '',
    [string]$Renderer = '',
    [ValidateRange(0, 10)]
    [int]$SurfaceScale = 0,
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
    [string]$CaptureDirectory = ''
)

$ErrorActionPreference = 'Stop'
$existingXemu = @(Get-Process -Name xemu -ErrorAction SilentlyContinue)
if ($existingXemu.Count -ne 0) {
    throw "Refusing to launch while $($existingXemu.Count) xemu process(es) exist."
}

$captureDirectory = if ($CaptureDirectory) {
    [System.IO.Path]::GetFullPath($CaptureDirectory)
} elseif ($ConfigPath) {
    Join-Path ([System.IO.Path]::GetDirectoryName(
            [System.IO.Path]::GetFullPath($ConfigPath))) 'launch-artifacts'
} else {
    'C:\xemu-lab\captures\retail-snapshot-launch'
}
New-Item -ItemType Directory -Path $captureDirectory -Force | Out-Null
$stdoutPath = Join-Path $captureDirectory 'stdout.txt'
$stderrPath = Join-Path $captureDirectory 'stderr.txt'
Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
$globalConfigPath = Join-Path $env:APPDATA 'xemu\xemu\xemu.toml'
$configPath = if ($ConfigPath) {
    if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
        throw "The requested xemu configuration was not found: $ConfigPath"
    }
    (Resolve-Path -LiteralPath $ConfigPath).Path
} else {
    if (-not (Test-Path -LiteralPath $globalConfigPath -PathType Leaf)) {
        throw "xemu configuration was not found: $globalConfigPath"
    }
    (Resolve-Path -LiteralPath $globalConfigPath).Path
}
$xemuArguments = @(
    '-name', 'xemu-capture,debug-threads=on',
    '-config_path', $configPath
)
if ($GuestTraceLog) {
    $traceDirectory = Split-Path -Parent $GuestTraceLog
    if ($traceDirectory -and -not (Test-Path -LiteralPath $traceDirectory)) {
        New-Item -ItemType Directory -Path $traceDirectory -Force | Out-Null
    }
    $xemuArguments += @('-msg','timestamp=on','-d','trace:nv2a_pgraph_flip_increment_write','-D',$GuestTraceLog)
}
if ($LaunchMode -eq 'Snapshot') {
    if ([string]::IsNullOrWhiteSpace($Snapshot)) {
        throw 'Snapshot launch mode requires -Snapshot.'
    }
    $xemuArguments += @('-loadvm', $Snapshot)
} elseif (-not $Disc) {
    throw 'FreshBoot launch mode requires -Disc.'
}
if ($Disc) {
    if (-not (Test-Path -LiteralPath $Disc -PathType Leaf)) {
        throw "Disc image was not found: $Disc"
    }
    if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
        throw "xemu configuration was not found: $configPath"
    }
    if ($Disc.Contains("'")) {
        throw "Disc path cannot be represented by the current TOML writer: $Disc"
    }
    $configLines = [System.IO.File]::ReadAllLines($configPath)
    $dvdLineIndex = -1
    for ($i = 0; $i -lt $configLines.Length; $i++) {
        if ($configLines[$i] -match '^\s*dvd_path\s*=') {
            $dvdLineIndex = $i
            break
        }
    }
    if ($dvdLineIndex -lt 0) {
        throw "dvd_path was not found in xemu configuration: $configPath"
    }
    $wantedDvdLine = "dvd_path = '$Disc'"
    if ($configLines[$dvdLineIndex] -ne $wantedDvdLine) {
        $configLines[$dvdLineIndex] = $wantedDvdLine
        $temporaryConfig = $configPath + '.xemu-lab.tmp'
        $backupConfig = $configPath + '.xemu-lab.bak'
        try {
            [System.IO.File]::WriteAllLines(
                $temporaryConfig,
                $configLines,
                [System.Text.UTF8Encoding]::new($false)
            )
            # A real backup path works under both Windows PowerShell 5.1 and
            # PowerShell 7. File.Replace(..., $null) fails on the latter.
            [System.IO.File]::Replace(
                $temporaryConfig,
                $configPath,
                $backupConfig
            )
        } finally {
            Remove-Item -LiteralPath $temporaryConfig, $backupConfig `
                -Force -ErrorAction SilentlyContinue
        }
    }
    # The configured dvd_path is used for both modes. Do not pass -dvd_path
    # with -loadvm: replacing the optical device while restoring a snapshot
    # changes saved device state and can trip APU asserts.
}
if ($Renderer -or $SurfaceScale -gt 0) {
    $configLines = [System.Collections.Generic.List[string]]::new()
    $configLines.AddRange([string[]][System.IO.File]::ReadAllLines($configPath))
    $changed = $false

    if ($Renderer) {
        $rendererFound = $false
        if ($Renderer -notin @('OPENGL', 'VULKAN')) {
            throw "Unsupported renderer: $Renderer"
        }
        for ($i = 0; $i -lt $configLines.Count; $i++) {
            if ($configLines[$i] -match '^\s*renderer\s*=') {
                $rendererFound = $true
                $wanted = "renderer = '$Renderer'"
                if ($configLines[$i] -ne $wanted) {
                    $configLines[$i] = $wanted
                    $changed = $true
                }
                break
            }
        }
        if (-not $rendererFound) {
            $displaySection = $configLines.IndexOf('[display]')
            if ($displaySection -lt 0) {
                $insertBefore = $configLines.IndexOf('[display.vulkan]')
                if ($insertBefore -lt 0) {
                    $insertBefore = $configLines.Count
                }
                $configLines.Insert($insertBefore, '')
                $configLines.Insert($insertBefore, "renderer = '$Renderer'")
                $configLines.Insert($insertBefore, '[display]')
            } else {
                $configLines.Insert($displaySection + 1, "renderer = '$Renderer'")
            }
            $changed = $true
        }
    }

    if ($SurfaceScale -gt 0) {
        $scaleFound = $false
        for ($i = 0; $i -lt $configLines.Count; $i++) {
            if ($configLines[$i] -match '^\s*surface_scale\s*=') {
                $scaleFound = $true
                $wanted = "surface_scale = $SurfaceScale"
                if ($configLines[$i] -ne $wanted) {
                    $configLines[$i] = $wanted
                    $changed = $true
                }
                break
            }
        }
        if (-not $scaleFound) {
            $qualitySection = $configLines.IndexOf('[display.quality]')
            if ($qualitySection -ge 0) {
                $configLines.Insert(
                    $qualitySection + 1, "surface_scale = $SurfaceScale"
                )
            } else {
                $configLines.Add('')
                $configLines.Add('[display.quality]')
                $configLines.Add("surface_scale = $SurfaceScale")
            }
            $changed = $true
        }
    }

    if ($changed) {
        $temporaryConfig = $configPath + '.xemu-lab-settings.tmp'
        $backupConfig = $configPath + '.xemu-lab-settings.bak'
        try {
            [System.IO.File]::WriteAllLines(
                $temporaryConfig, $configLines,
                [System.Text.UTF8Encoding]::new($false)
            )
            [System.IO.File]::Replace($temporaryConfig, $configPath, $backupConfig)
        } finally {
            Remove-Item -LiteralPath $temporaryConfig, $backupConfig `
                -Force -ErrorAction SilentlyContinue
        }
    }
}

# Snapshots selected after a physical controller disconnect can otherwise
# remain on a reconnect prompt while still producing plausible frame logs.
$configLines = [System.Collections.Generic.List[string]]::new()
$configLines.AddRange([string[]][System.IO.File]::ReadAllLines($configPath))
$inputSection = $configLines.IndexOf('[input.bindings]')
$inputChanged = $false
if ($inputSection -lt 0) {
    $insertBefore = $configLines.Count
    for ($i = 0; $i -lt $configLines.Count; $i++) {
        if ($configLines[$i] -match '^\[') {
            $insertBefore = $i
            break
        }
    }
    $configLines.Insert($insertBefore, '')
    $configLines.Insert($insertBefore, "port1 = 'keyboard'")
    $configLines.Insert($insertBefore, '[input.bindings]')
    $inputChanged = $true
} else {
    $port1Index = -1
    for ($i = $inputSection + 1; $i -lt $configLines.Count; $i++) {
        if ($configLines[$i] -match '^\[') {
            break
        }
        if ($configLines[$i] -match '^\s*port1\s*=') {
            $port1Index = $i
            break
        }
    }
    if ($port1Index -lt 0) {
        $configLines.Insert($inputSection + 1, "port1 = 'keyboard'")
        $inputChanged = $true
    } elseif ($configLines[$port1Index] -ne "port1 = 'keyboard'") {
        $configLines[$port1Index] = "port1 = 'keyboard'"
        $inputChanged = $true
    }
}
# This opt-in is currently known to be bugged. Never let stale user config
# silently enable it in a performance or correctness run.
for ($i = 0; $i -lt $configLines.Count; $i++) {
    if ($configLines[$i] -match '^\s*reduce_host_cpu_usage\s*=') {
        if ($configLines[$i] -ne 'reduce_host_cpu_usage = false') {
            $configLines[$i] = 'reduce_host_cpu_usage = false'
            $inputChanged = $true
        }
        break
    }
}
if ($inputChanged) {
    $temporaryConfig = $configPath + '.xemu-lab-input.tmp'
    $backupConfig = $configPath + '.xemu-lab-input.bak'
    try {
        [System.IO.File]::WriteAllLines(
            $temporaryConfig, $configLines,
            [System.Text.UTF8Encoding]::new($false)
        )
        [System.IO.File]::Replace($temporaryConfig, $configPath, $backupConfig)
    } finally {
        Remove-Item -LiteralPath $temporaryConfig, $backupConfig `
            -Force -ErrorAction SilentlyContinue
    }
}
$startParameters = @{
    FilePath = $Xemu
    ArgumentList = $xemuArguments
    RedirectStandardOutput = $stdoutPath
    RedirectStandardError = $stderrPath
    PassThru = $true
}
$childEnvironment = @{
    XEMU_FLIP_LOG = $FlipLog
    XEMU_FRAME_LOG = $FrameLog
    XEMU_PERF_EVENT_LOG = $EventLog
    XEMU_VK_PERF_LOG = $VkPerfLog
    XEMU_LAB_PERFLOG = ''
    XEMU_PERF_TELEMETRY_PATH = ''
    XEMU_PERF_TELEMETRY_LEVEL = ''
    XEMU_VK_VERTEX_STAGING_INITIAL_MIB = $(
        if ($VertexStagingInitialMiB -gt 0) {
            [string]$VertexStagingInitialMiB
        } else {
            ''
        }
    )
    XEMU_VK_REUSE_IDENTICAL_INDEX_PAYLOADS = $(
        if ($ReuseIdenticalIndexPayloads -eq 'Enabled') { '1' } else { '' }
    )
    XEMU_VK_EXPAND_DESCRIPTOR_SETS = $(
        if ($ExpandDescriptorSets -eq 'Enabled') { '1' } else { '' }
    )
    XEMU_TCG_TLB_DIRTY_HOST_PAGE_FILTER = $(
        if ($TlbDirtyHostPageFilter -eq 'Enabled') { '1' } else { '' }
    )
    XEMU_VK_SKIP_EQUIVALENT_TEXTURE_SCALE_UPDATES = $(
        if ($SkipEquivalentTextureScaleUpdates -eq 'Enabled') { '1' } else { '' }
    )
}
$savedEnvironment = @{}
$process = $null
try {
    foreach ($name in $childEnvironment.Keys) {
        $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable(
            $name, 'Process')
    }
    try {
        foreach ($name in $childEnvironment.Keys) {
            [Environment]::SetEnvironmentVariable(
                $name, $childEnvironment[$name], 'Process')
        }
        # Windows PowerShell 5.1 has no Start-Process -Environment parameter.
        # Start the child while the current process contains the sanitized values;
        # restore the runner environment immediately afterward.
        $process = Start-Process @startParameters
    } finally {
        foreach ($name in $savedEnvironment.Keys) {
            [Environment]::SetEnvironmentVariable(
                $name, $savedEnvironment[$name], 'Process')
        }
    }

    Add-Type -AssemblyName Microsoft.VisualBasic
    $deadline = [DateTime]::UtcNow.AddSeconds(15)
    $focused = $false
    do {
        Start-Sleep -Milliseconds 100
        $process.Refresh()
        if ($process.HasExited) {
            break
        }
        try {
            $focused = [Microsoft.VisualBasic.Interaction]::AppActivate($process.Id)
        } catch {
            $focused = $false
        }
    } until ($focused -or [DateTime]::UtcNow -ge $deadline)

    [pscustomobject]@{
        ProcessId = $process.Id
        Exited = $process.HasExited
        Focused = $focused
        LaunchMode = $LaunchMode
        Snapshot = if ($LaunchMode -eq 'Snapshot') { $Snapshot } else { $null }
        ConfigPath = $configPath
        Xemu = $Xemu
        FlipLog = $FlipLog
        GuestTraceLog = $GuestTraceLog
        FrameLog = $FrameLog
        EventLog = $EventLog
        Disc = $Disc
        Renderer = $Renderer
        SurfaceScale = $SurfaceScale
        VertexStagingInitialMiB = $VertexStagingInitialMiB
        ReuseIdenticalIndexPayloads = $ReuseIdenticalIndexPayloads
        ExpandDescriptorSets = $ExpandDescriptorSets
        TlbDirtyHostPageFilter = $TlbDirtyHostPageFilter
        SkipEquivalentTextureScaleUpdates = $SkipEquivalentTextureScaleUpdates
        Stdout = $stdoutPath
        Stderr = $stderrPath
    }
} catch {
    if ($process -and -not $process.HasExited) {
        try {
            $process.Kill()
            [void]$process.WaitForExit(30000)
        } catch {
            # Preserve the launch/focus failure after attempting owned cleanup.
        }
    }
    throw
}
