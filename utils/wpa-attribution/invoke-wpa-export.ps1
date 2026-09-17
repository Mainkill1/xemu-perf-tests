[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string] $Exporter,
    [Parameter(Mandatory)] [string] $Etl,
    [Parameter(Mandatory)] [string] $Profile,
    [Parameter(Mandatory)] [string] $OutputDirectory,
    [Parameter(Mandatory)] [long] $StartNs,
    [Parameter(Mandatory)] [long] $EndNs,
    [Parameter(Mandatory)] [string] $Prefix,
    [Parameter(Mandatory)] [ValidateRange(1, 32)] [int] $ExpectedCsvCount,
    [long] $MaximumOutputBytes = 268435456
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
if ($StartNs -lt 0 -or $EndNs -le $StartNs) { throw 'Invalid nanosecond range' }
foreach ($path in @($Exporter, $Etl, $Profile)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing input: $path" }
}
if (Test-Path -LiteralPath $OutputDirectory) { throw 'Refusing a stale output directory' }
if (@(Get-Process wpa,wpaexporter,xperf -ErrorAction SilentlyContinue).Count) {
    throw 'A WPA analysis process is already running'
}
New-Item -ItemType Directory -Path $OutputDirectory | Out-Null
$stdout = Join-Path $OutputDirectory 'wpaexporter.stdout.txt'
$stderr = Join-Path $OutputDirectory 'wpaexporter.stderr.txt'
$argsForExporter = @(
    '-i', $Etl,
    '-symbols', '-symcacheonly',
    '-range', [string]$StartNs, [string]$EndNs,
    '-profile', $Profile,
    '-outputfolder', $OutputDirectory,
    '-outputformat', 'CSV',
    '-prefix', $Prefix
)
$savedErrorActionPreference = $ErrorActionPreference
try {
    # Windows PowerShell promotes native stderr records when Stop is active.
    # WPAExporter writes diagnostics to stderr even on a successful export.
    $ErrorActionPreference = 'Continue'
    & $Exporter @argsForExporter 1> $stdout 2> $stderr
    $exitCode = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $savedErrorActionPreference
}
$errorMarkers = @(
    Select-String -LiteralPath $stderr -Pattern @(
        'Error exporting profile', 'Unable to export',
        'Object reference not set to an instance of an object',
        'There was an error loading the file', 'Error loading profile'
    ) -ErrorAction SilentlyContinue | ForEach-Object { $_.Line }
)
$outputs = @(
    Get-ChildItem -LiteralPath $OutputDirectory -File | ForEach-Object {
        [ordered]@{
            name = $_.Name
            bytes = $_.Length
            sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
)
$csvFiles = @(Get-ChildItem -LiteralPath $OutputDirectory -Filter '*.csv' -File)
$csvTerminalCrLf = [ordered]@{}
foreach ($csv in $csvFiles) {
    $bytes = [IO.File]::ReadAllBytes($csv.FullName)
    $csvTerminalCrLf[$csv.Name] = (
        $bytes.Length -ge 2 -and $bytes[$bytes.Length - 2] -eq 13 -and
        $bytes[$bytes.Length - 1] -eq 10
    )
}
$totalBytes = [long](($outputs | ForEach-Object { $_.bytes } | Measure-Object -Sum).Sum)
$result = [ordered]@{
    exporter_sha256 = (Get-FileHash -LiteralPath $Exporter -Algorithm SHA256).Hash.ToLowerInvariant()
    etl_sha256 = (Get-FileHash -LiteralPath $Etl -Algorithm SHA256).Hash.ToLowerInvariant()
    profile_sha256 = (Get-FileHash -LiteralPath $Profile -Algorithm SHA256).Hash.ToLowerInvariant()
    range_ns = @($StartNs, $EndNs)
    command_arguments = $argsForExporter
    exit_code = $exitCode
    error_markers = $errorMarkers
    outputs = $outputs
    csv_count = $csvFiles.Count
    expected_csv_count = $ExpectedCsvCount
    csv_terminal_crlf = $csvTerminalCrLf
    total_output_bytes = $totalBytes
    output_size_validation = 'post-export; this guard does not enforce a runtime file-size limit'
    row_shape_validation = 'required downstream before quantitative use'
    remaining_processes = @(
        Get-Process wpa,wpaexporter,xperf -ErrorAction SilentlyContinue |
            Select-Object Name,Id,SessionId
    )
}
$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (
    Join-Path $OutputDirectory 'export-manifest.json'
) -Encoding utf8
$result | ConvertTo-Json -Depth 8
if ($exitCode -ne 0 -or $errorMarkers.Count -or
    $csvFiles.Count -ne $ExpectedCsvCount -or
    @($csvTerminalCrLf.Values | Where-Object { -not $_ }).Count -or
    $totalBytes -gt $MaximumOutputBytes -or $result.remaining_processes.Count) {
    exit 50
}
