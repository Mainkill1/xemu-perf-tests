Set-StrictMode -Version Latest

function Save-CaptureClockAnchor {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$AnchorPath,

        [Parameter(Mandatory)]
        [string]$Phase,

        [Parameter(Mandatory)]
        [hashtable]$SourceIdentity,

        [Parameter(Mandatory)]
        [hashtable]$BinaryIdentity
    )

    $absolutePath = [System.IO.Path]::GetFullPath($AnchorPath)
    $directory = [System.IO.Path]::GetDirectoryName($absolutePath)
    if (-not (Test-Path -LiteralPath $directory -PathType Container)) {
        throw "Anchor directory does not exist: $directory"
    }
    if (Test-Path -LiteralPath $absolutePath) {
        throw "Anchor path already exists: $absolutePath"
    }

    $qpcBefore = [System.Diagnostics.Stopwatch]::GetTimestamp()
    $utcSample = [DateTime]::UtcNow
    $qpcAfter = [System.Diagnostics.Stopwatch]::GetTimestamp()
    $anchor = [ordered]@{
        schema_version = 1
        type = 'capture_clock_anchor'
        phase = $Phase
        qpc_before = $qpcBefore
        qpc_after = $qpcAfter
        qpc_frequency_hz = [System.Diagnostics.Stopwatch]::Frequency
        utc_sample = $utcSample.ToString('O')
        clock_source = [ordered]@{
            qpc = 'System.Diagnostics.Stopwatch.GetTimestamp'
            utc = 'System.DateTime.UtcNow'
        }
        source_identity = $SourceIdentity
        binary_identity = $BinaryIdentity
    }
    $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes(
        (($anchor | ConvertTo-Json -Depth 8 -Compress) + "`n"))
    $temporaryPath = Join-Path $directory (
        ('.' + [System.IO.Path]::GetFileName($absolutePath) + '.' +
         [guid]::NewGuid().ToString('N') + '.tmp'))
    $stream = $null

    try {
        $stream = [System.IO.FileStream]::new(
            $temporaryPath, [System.IO.FileMode]::CreateNew,
            [System.IO.FileAccess]::Write, [System.IO.FileShare]::None,
            4096, [System.IO.FileOptions]::WriteThrough)
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
        $stream.Dispose()
        $stream = $null
        [System.IO.File]::Move($temporaryPath, $absolutePath)
    } finally {
        if ($null -ne $stream) {
            $stream.Dispose()
        }
        if (Test-Path -LiteralPath $temporaryPath) {
            Remove-Item -LiteralPath $temporaryPath -Force
        }
    }
}

function Resolve-CaptureLaunchArtifacts {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$CellPath,

        [Parameter(Mandatory)]
        [ValidateSet('VULKAN', 'OPENGL')]
        [string]$Renderer
    )

    $cellRoot = [System.IO.Path]::GetFullPath($CellPath)
    if (-not (Test-Path -LiteralPath $cellRoot -PathType Container)) {
        throw "Capture cell directory does not exist: $cellRoot"
    }
    $controlPath = Join-Path $cellRoot 'control.json'
    if (-not (Test-Path -LiteralPath $controlPath -PathType Leaf)) {
        throw "Capture control file is missing: $controlPath"
    }
    try {
        $control = Get-Content -LiteralPath $controlPath -Raw -ErrorAction Stop |
            ConvertFrom-Json -ErrorAction Stop
    } catch {
        throw "Capture control file is not valid JSON: $controlPath"
    }
    if ($null -eq $control -or $control -is [array]) {
        throw "Capture control file must contain one JSON object: $controlPath"
    }

    $schemaProperty = $control.PSObject.Properties['schema_version']
    if ($null -eq $schemaProperty -or $schemaProperty.Value -ne 1) {
        throw "Capture control schema_version must be 1: $controlPath"
    }
    $statusProperty = $control.PSObject.Properties['status']
    if ($null -eq $statusProperty -or $statusProperty.Value -cne 'closed') {
        throw "Capture control status must be closed: $controlPath"
    }
    $launchCountProperty = $control.PSObject.Properties['launches']
    if ($null -eq $launchCountProperty -or $launchCountProperty.Value -ne 1) {
        throw "Capture control launches must be exactly 1: $controlPath"
    }
    $launchProperty = $control.PSObject.Properties['launch_dir']
    if ($null -eq $launchProperty -or [string]::IsNullOrWhiteSpace(
            [string]$launchProperty.Value)) {
        throw "Capture control file has no launch_dir: $controlPath"
    }

    $launchValue = [string]$launchProperty.Value
    if (-not [System.IO.Path]::IsPathRooted($launchValue)) {
        throw "Capture launch_dir must be an absolute canonical path: $launchValue"
    }
    $launchDirectory = [System.IO.Path]::GetFullPath($launchValue)
    $expectedLaunchDirectory = [System.IO.Path]::GetFullPath(
        (Join-Path $cellRoot 'launch-1'))
    if (-not [string]::Equals(
            $launchDirectory,
            $expectedLaunchDirectory,
            [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Capture launch_dir must be the canonical launch-1 directory: $launchDirectory"
    }
    if (-not (Test-Path -LiteralPath $launchDirectory -PathType Container)) {
        throw "Capture launch directory does not exist: $launchDirectory"
    }

    $requiredPaths = [ordered]@{
        result = Join-Path $cellRoot 'result.json'
        actions = Join-Path $cellRoot 'actions.jsonl'
        stderr = Join-Path $launchDirectory 'stderr.log'
        stdout = Join-Path $launchDirectory 'stdout.log'
        guest_flips = Join-Path $launchDirectory 'guest-flips.log'
        measurement_start_capture = Join-Path $launchDirectory 'measurement-start.capture.json'
        measurement_end_capture = Join-Path $launchDirectory 'measurement-end.capture.json'
        measurement_end_image = Join-Path $launchDirectory 'measurement-end.png'
    }
    foreach ($entry in $requiredPaths.GetEnumerator()) {
        if (-not (Test-Path -LiteralPath $entry.Value -PathType Leaf)) {
            throw "Capture required artifact is missing ($($entry.Key)): $($entry.Value)"
        }
    }
    $rendererName = $Renderer.ToUpperInvariant()
    $telemetryPath = $null
    $telemetryApplicable = $rendererName -ceq 'VULKAN'
    if ($telemetryApplicable) {
        $telemetryPath = Join-Path $cellRoot 'vulkan-perf.jsonl'
        if (-not (Test-Path -LiteralPath $telemetryPath -PathType Leaf)) {
            throw "Capture required artifact is missing (telemetry): $telemetryPath"
        }
    }

    return [pscustomobject][ordered]@{
        control = $controlPath
        result = $requiredPaths.result
        actions = $requiredPaths.actions
        renderer = $rendererName
        telemetry_applicable = $telemetryApplicable
        telemetry = $telemetryPath
        launch_dir = $launchDirectory
        stderr = $requiredPaths.stderr
        stdout = $requiredPaths.stdout
        guest_flips = $requiredPaths.guest_flips
        measurement_start_capture = $requiredPaths.measurement_start_capture
        measurement_end_capture = $requiredPaths.measurement_end_capture
        measurement_end_image = $requiredPaths.measurement_end_image
    }
}

function Assert-CaptureProcessQueryIdle {
    [CmdletBinding()]
    param(
        [AllowNull()]
        [object]$ProcessQueryResult
    )

    $normalized = @(
        foreach ($process in $ProcessQueryResult) {
            if ($null -ne $process) {
                $process
            }
        }
    )
    if ($normalized.Count -ne 0) {
        throw "Capture process query found $($normalized.Count) conflicting process record(s)"
    }
}
