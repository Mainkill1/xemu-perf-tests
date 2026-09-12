$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Get-Sha256([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required file is missing: $Path"
    }
    (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}

function Write-JsonAtomic([string]$Path, [object]$Value) {
    $parent = Split-Path -Parent $Path
    if ($parent) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    $temporary = "$Path.tmp"
    $Value | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $temporary -Encoding utf8
    Move-Item -LiteralPath $temporary -Destination $Path -Force
}

function Assert-NoPlaceholders([object]$Value, [string]$Context = 'campaign') {
    $json = $Value | ConvertTo-Json -Depth 20
    $matches = @([regex]::Matches($json, '__[A-Z0-9_]+__') |
        ForEach-Object Value | Sort-Object -Unique)
    if ($matches.Count -ne 0) {
        throw "$Context has unresolved placeholders: $($matches -join ', ')"
    }
}

function Read-BuildInfo([string]$Path) {
    $values = [ordered]@{}
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^([A-Z][A-Z0-9_]*)=(.*)$') {
            $values[$Matches[1]] = $Matches[2].Trim()
        }
    }
    $values
}

function Assert-BuildContract([System.Collections.IDictionary]$Build) {
    foreach ($name in @('Role', 'LogicalCommit', 'SourceCommit', 'Xemu',
                         'XemuSha256', 'BuildInfo')) {
        if ([string]::IsNullOrWhiteSpace([string]$Build[$name])) {
            throw "$($Build.Role) is missing $name"
        }
    }
    if ($Build.LogicalCommit -notmatch '^[0-9a-f]{40}$' -or
        $Build.SourceCommit -notmatch '^[0-9a-f]{40}$' -or
        $Build.XemuSha256 -notmatch '^[0-9a-f]{64}$') {
        throw "$($Build.Role) contains a malformed source or executable identity"
    }
    $actualXemu = Get-Sha256 $Build.Xemu
    if ($actualXemu -ne $Build.XemuSha256) {
        throw "$($Build.Role) xemu hash mismatch: $actualXemu"
    }
    $info = Read-BuildInfo $Build.BuildInfo
    foreach ($name in @('SOURCE_SHA', 'SOURCE_TREE', 'XEMU_SHA256')) {
        if (-not $info.Contains($name)) {
            throw "$($Build.Role) BUILD_INFO lacks $name"
        }
    }
    if ($info.SOURCE_SHA -ne $Build.SourceCommit -or
        $info.XEMU_SHA256 -ne $Build.XemuSha256) {
        throw "$($Build.Role) BUILD_INFO does not identify the pinned binary"
    }
    if ([string]::IsNullOrWhiteSpace([string]$Build.Tree)) {
        $Build.Tree = $info.SOURCE_TREE
    } elseif ($Build.Tree -ne $info.SOURCE_TREE) {
        throw "$($Build.Role) source tree mismatch"
    }
    if ($Build.Tree -notmatch '^[0-9a-f]{40}$') {
        throw "$($Build.Role) has a malformed tree identity"
    }
    [ordered]@{
        role = $Build.Role
        logical_commit = $Build.LogicalCommit
        source_commit = $Build.SourceCommit
        tree = $Build.Tree
        xemu_sha256 = $Build.XemuSha256
        build_info_sha256 = Get-Sha256 $Build.BuildInfo
    }
}

function Assert-Hash([string]$Path, [string]$Expected, [string]$Label) {
    $actual = Get-Sha256 $Path
    if ($actual -ne $Expected) {
        throw "$Label hash mismatch: expected $Expected, observed $actual"
    }
}

function Assert-AutoGpuConfig([string]$Path) {
    $text = Get-Content -LiteralPath $Path -Raw
    foreach ($key in @('device_uuid', 'preferred_physical_device')) {
        $pattern = '(?m)^\s*{0}\s*=\s*[''"]([^''"]*)[''"]\s*(?:#.*)?$' -f
            [regex]::Escape($key)
        $assignments = @([regex]::Matches($text, $pattern))
        if ($assignments.Count -gt 1) {
            throw "Ambiguous $key selection in $Path"
        }
        if ($assignments.Count -eq 1 -and
            -not [string]::IsNullOrWhiteSpace($assignments[0].Groups[1].Value)) {
            throw "GPU must remain auto-selected; $key is pinned in $Path"
        }
    }
}

function Get-HostAdmission([System.Collections.IDictionary]$Campaign) {
    if ([Diagnostics.Process]::GetCurrentProcess().SessionId -ne
        $Campaign.Host.RequiredSessionId -or -not [Environment]::UserInteractive) {
        throw 'The campaign requires interactive Session 1 through GuiTestConsole.'
    }
    $os = Get-CimInstance Win32_OperatingSystem
    $freeGiB = [math]::Round(([double]$os.FreePhysicalMemory * 1KB) / 1GB, 3)
    if ($freeGiB -lt [double]$Campaign.Host.MinimumFreeMemoryGiB) {
        throw "Memory admission failed: $freeGiB GiB free"
    }
    $gpus = @(Get-CimInstance Win32_VideoController | ForEach-Object {
        [ordered]@{
            name = $_.Name
            pnp_device_id = $_.PNPDeviceID
            driver_version = $_.DriverVersion
            driver_date = if ($_.DriverDate) { $_.DriverDate.ToUniversalTime().ToString('o') } else { $null }
        }
    })
    if (-not @($gpus | Where-Object { $_.name -match 'NVIDIA' })) {
        throw 'The required NVIDIA comparison adapter is not present.'
    }
    [ordered]@{
        checked_utc = [DateTimeOffset]::UtcNow.ToString('o')
        free_memory_gib = $freeGiB
        minimum_free_memory_gib = $Campaign.Host.MinimumFreeMemoryGiB
        session_id = [Diagnostics.Process]::GetCurrentProcess().SessionId
        gpu_policy = $Campaign.Host.GpuPolicy
        expected_auto_adapter_vendor = $Campaign.Host.ExpectedAutoAdapterVendor
        adapters = $gpus
        status = 'passed'
    }
}

function Get-CampaignProcesses([System.Collections.IDictionary]$Campaign) {
    $resultsRoot = [IO.Path]::GetFullPath($Campaign.ResultsRoot)
    @(Get-Process -Name xemu -ErrorAction SilentlyContinue | Where-Object {
        try {
            $_.Path -and [IO.Path]::GetFullPath($_.Path).StartsWith(
                $resultsRoot, [StringComparison]::OrdinalIgnoreCase)
        } catch { $false }
    })
}

function Assert-HostIdle([System.Collections.IDictionary]$Campaign, [string]$Scope) {
    $xemu = @(Get-Process -Name xemu -ErrorAction SilentlyContinue)
    $traces = @(Get-Process -Name $Campaign.Host.TraceProcessNames -ErrorAction SilentlyContinue)
    if ($xemu.Count -ne 0 -or $traces.Count -ne 0) {
        $active = @($xemu + $traces | ForEach-Object { "$($_.ProcessName):$($_.Id)" })
        throw "$Scope found an active emulator/trace process: $($active -join ', ')"
    }
}

function Invoke-CampaignCleanup(
    [System.Collections.IDictionary]$Campaign,
    [string]$Scope,
    [string[]]$PrivateHdds = @()
) {
    $errors = @()
    $terminated = @()
    foreach ($process in @(Get-CampaignProcesses $Campaign)) {
        $terminated += $process.Id
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        Wait-Process -Id $process.Id -Timeout 20 -ErrorAction SilentlyContinue
    }
    $tracePids = @()
    foreach ($process in @(Get-Process -Name $Campaign.Host.TraceProcessNames -ErrorAction SilentlyContinue)) {
        $tracePids += $process.Id
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        Wait-Process -Id $process.Id -Timeout 20 -ErrorAction SilentlyContinue
    }
    foreach ($path in $PrivateHdds) {
        if ($path -and (Test-Path -LiteralPath $path)) {
            try { Remove-Item -LiteralPath $path -Force } catch {
                $errors += "Failed to remove owned private HDD ${path}: $($_.Exception.Message)"
            }
        }
        if ($path -and (Test-Path -LiteralPath $path)) {
            $errors += "Owned private HDD remains: $path"
        }
    }
    $remainingXemu = @(Get-CampaignProcesses $Campaign | ForEach-Object Id)
    $remainingTraces = @(Get-Process -Name $Campaign.Host.TraceProcessNames `
        -ErrorAction SilentlyContinue | ForEach-Object Id)
    if ($remainingXemu.Count) { $errors += "Owned xemu remains: $($remainingXemu -join ',')" }
    if ($remainingTraces.Count) { $errors += "Trace process remains: $($remainingTraces -join ',')" }
    [ordered]@{
        scope = $Scope
        terminated_xemu_pids = $terminated
        terminated_trace_pids = $tracePids
        private_hdds = $PrivateHdds
        status = if ($errors.Count) { 'failed' } else { 'passed' }
        errors = $errors
        completed_utc = [DateTimeOffset]::UtcNow.ToString('o')
    }
}

function New-PortableBuild(
    [System.Collections.IDictionary]$Campaign,
    [System.Collections.IDictionary]$Build,
    [string]$Name,
    [string]$BaseConfig = '',
    [ValidateSet('Enabled', 'Disabled')][string]$ShaderCache = 'Enabled',
    [ValidateSet('Off', 'On')][string]$HybridUbershaders = 'Off'
) {
    $directory = Join-Path $Campaign.ResultsRoot "profiles\$Name"
    if (Test-Path -LiteralPath $directory) {
        throw "Portable profile already exists: $directory"
    }
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
    $xemu = Join-Path $directory 'xemu.exe'
    Copy-Item -LiteralPath $Build.Xemu -Destination $xemu
    Copy-Item -LiteralPath $Build.BuildInfo -Destination (Join-Path $directory 'BUILD_INFO.txt')
    if ($BaseConfig) {
        Assert-AutoGpuConfig $BaseConfig
        Copy-Item -LiteralPath $BaseConfig -Destination (Join-Path $directory 'xemu.toml')
    } else {
        Set-Content -LiteralPath (Join-Path $directory 'xemu.toml') -Value '' -Encoding utf8
    }
    # Native capture receives this profile as its immutable base config. Keep
    # both restart-only controls explicit in every isolated profile.
    $cacheValue = if ($ShaderCache -eq 'Enabled') { 'true' } else { 'false' }
    $hybridValue = if ($HybridUbershaders -eq 'On') { 'true' } else { 'false' }
    Add-Content -LiteralPath (Join-Path $directory 'xemu.toml') -Value @(
        '',
        '[perf]',
        "cache_shaders = $cacheValue",
        '',
        '[tweaks]',
        "vk_hybrid_ubershaders = $hybridValue"
    ) -Encoding utf8
    Get-PortableBuild $Campaign $Build $Name $ShaderCache $HybridUbershaders
}

function Get-PortableBuild(
    [System.Collections.IDictionary]$Campaign,
    [System.Collections.IDictionary]$Build,
    [string]$Name,
    [ValidateSet('Enabled', 'Disabled')][string]$ShaderCache = 'Enabled',
    [ValidateSet('Off', 'On')][string]$HybridUbershaders = 'Off'
) {
    $directory = Join-Path $Campaign.ResultsRoot "profiles\$Name"
    $xemu = Join-Path $directory 'xemu.exe'
    $buildInfo = Join-Path $directory 'BUILD_INFO.txt'
    $config = Join-Path $directory 'xemu.toml'
    foreach ($path in @($xemu, $buildInfo, $config)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Incomplete portable profile: $path"
        }
    }
    Assert-Hash $xemu $Build.XemuSha256 "$($Build.Role) portable xemu"
    $info = Read-BuildInfo $buildInfo
    if ($info.SOURCE_SHA -ne $Build.SourceCommit -or
        $info.SOURCE_TREE -ne $Build.Tree -or
        $info.XEMU_SHA256 -ne $Build.XemuSha256) {
        throw "$($Build.Role) portable build identity mismatch"
    }
    [ordered]@{
        directory = $directory
        xemu = $xemu
        build_info = $buildInfo
        BuildInfo = $buildInfo
        profile_root = Join-Path $directory 'profile-env'
        role = $Build.Role
        shader_cache = $ShaderCache
        hybrid_ubershaders = $HybridUbershaders
    }
}

function Get-SpirvCacheReceipt([string]$SearchRoot) {
    if (-not (Test-Path -LiteralPath $SearchRoot)) { return $null }
    $files = @(Get-ChildItem -LiteralPath $SearchRoot -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^spirv-v[0-9]+-vk[0-9]+-spv[0-9]+\.bin$' })
    if ($files.Count -gt 1) {
        throw "Multiple target-qualified SPIR-V caches found below ${SearchRoot}: $($files.FullName -join ', ')"
    }
    if ($files.Count -eq 0) { return $null }
    [ordered]@{
        path = $files[0].FullName
        name = $files[0].Name
        bytes = $files[0].Length
        sha256 = Get-Sha256 $files[0].FullName
    }
}

function Get-SpirvStats([string]$LogPath) {
    if (-not (Test-Path -LiteralPath $LogPath -PathType Leaf)) { return $null }
    $line = @(Get-Content -LiteralPath $LogPath |
        Where-Object { $_ -match '^nv2a/vk: SPIR-V prewarm ' }) | Select-Object -Last 1
    if (-not $line) { return $null }
    if ($line -notmatch 'hits=(\d+) misses=(\d+) rejections=(\d+) fallbacks=(\d+) records=(\d+) source_bytes=(\d+) spirv_bytes=(\d+) loaded_bytes=(\d+) queued_bytes=(\d+) write=(\w+)') {
        throw "Malformed SPIR-V prewarm summary: $line"
    }
    [ordered]@{
        line = $line
        hits = [uint64]$Matches[1]
        misses = [uint64]$Matches[2]
        rejections = [uint64]$Matches[3]
        fallbacks = [uint64]$Matches[4]
        records = [uint64]$Matches[5]
        source_bytes = [uint64]$Matches[6]
        spirv_bytes = [uint64]$Matches[7]
        loaded_bytes = [uint64]$Matches[8]
        queued_bytes = [uint64]$Matches[9]
        write = $Matches[10]
    }
}

function Get-AdapterEvidence(
    [ValidateSet('opengl', 'vulkan')][string]$Renderer,
    [string]$LogPath,
    [string]$ExpectedVendor
) {
    if (-not (Test-Path -LiteralPath $LogPath -PathType Leaf)) {
        throw "Renderer log is missing: $LogPath"
    }
    $lines = @(Get-Content -LiteralPath $LogPath)
    if ($Renderer -eq 'vulkan') {
        $line = @($lines | Where-Object {
            $_ -match '^Selected physical device:\s*'
        }) | Select-Object -Last 1
        if (-not $line -or $line -notmatch '^Selected physical device:\s*(.+?)(?:\s+\[[^]]+\])?$') {
            throw 'Vulkan selected-device evidence is missing.'
        }
        $name = $Matches[1].Trim()
        if ($name -notmatch [regex]::Escape($ExpectedVendor)) {
            throw "Vulkan auto-selected '$name', expected $ExpectedVendor."
        }
        return [ordered]@{ renderer='vulkan'; selected=$name; source_line=$line; status='passed' }
    }
    $vendorLine = @($lines | Where-Object { $_ -match '^GL_VENDOR:\s*' }) |
        Select-Object -Last 1
    $rendererLine = @($lines | Where-Object { $_ -match '^GL_RENDERER:\s*' }) |
        Select-Object -Last 1
    if (-not $vendorLine -or -not $rendererLine) {
        throw 'OpenGL adapter evidence is missing.'
    }
    if (("$vendorLine $rendererLine") -notmatch [regex]::Escape($ExpectedVendor)) {
        throw "OpenGL auto-selection is not ${ExpectedVendor}: $vendorLine; $rendererLine"
    }
    [ordered]@{
        renderer = 'opengl'
        vendor = $vendorLine.Substring('GL_VENDOR:'.Length).Trim()
        selected = $rendererLine.Substring('GL_RENDERER:'.Length).Trim()
        source_line = "$vendorLine; $rendererLine"
        status = 'passed'
    }
}

function Assert-CachePhase(
    [string]$Phase,
    [object]$Before,
    [object]$After,
    [object]$Stats
) {
    if ($Phase -eq 'none') { return }
    if ($Phase -eq 'cold') {
        if ($Before) { throw 'Cold cell started with a cache.' }
        if (-not $After -or -not $Stats -or $Stats.misses -le 0 -or
            $Stats.rejections -ne 0 -or $Stats.fallbacks -ne 0 -or
            $Stats.write -ne 'published') {
            throw 'Cold cell did not compile and publish a cache.'
        }
        return
    }
    if ($Phase -eq 'warm') {
        # A repeat launch may reach a source the cold launch did not.  Warm
        # admission proves that the loaded cache served known artifacts;
        # misses remain visible in the cell record and are republished.
        if (-not $Before -or -not $After -or -not $Stats -or
            $Stats.hits -le 0 -or
            $Stats.rejections -ne 0 -or $Stats.fallbacks -ne 0 -or
            $Stats.loaded_bytes -le 0 -or $Stats.write -ne 'published') {
            throw 'Warm cell did not reload, serve, and republish a clean cache.'
        }
        return
    }
    throw "Unknown cache phase: $Phase"
}

function Get-ImprovementPercent([double]$Reference, [double]$Candidate, [bool]$HigherIsBetter) {
    if ($Reference -eq 0) { return $null }
    $value = if ($HigherIsBetter) {
        (($Candidate - $Reference) / [math]::Abs($Reference)) * 100.0
    } else {
        (($Reference - $Candidate) / [math]::Abs($Reference)) * 100.0
    }
    [math]::Round($value, 3)
}

function Format-Improvement($Value) {
    if ($null -eq $Value) { return 'n/a' }
    '{0:+0.000;-0.000;0.000}%' -f $Value
}
