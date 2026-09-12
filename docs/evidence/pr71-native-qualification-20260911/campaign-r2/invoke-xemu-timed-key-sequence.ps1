[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 2147483647)]
    [int]$ProcessId,

    [ValidateRange(0, 60)]
    [int]$BiosDelaySeconds = 10,

    [Parameter(Mandatory = $true)]
    [string[]]$KeySequence,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath,

    [string]$SendKeyTool = 'C:\xemu-lab\suite\send-xemu-key.ps1'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $SendKeyTool -PathType Leaf)) {
    throw "Key sender was not found: $SendKeyTool"
}
if ($KeySequence.Count -eq 0) {
    throw 'At least one timed key press is required.'
}

$outputDirectory = Split-Path -Parent $OutputPath
if ($outputDirectory) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}
Remove-Item -LiteralPath $OutputPath -Force -ErrorAction SilentlyContinue

$process = Get-Process -Id $ProcessId -ErrorAction Stop
$startedAt = [DateTime]::UtcNow
[ordered]@{
    schema_version = 1
    type = 'sequence'
    process_id = $ProcessId
    bios_delay_seconds = $BiosDelaySeconds
    key_sequence = $KeySequence
    started_at_utc = $startedAt.ToString('o')
} | ConvertTo-Json -Compress |
    Set-Content -LiteralPath $OutputPath -Encoding utf8

if ($BiosDelaySeconds -gt 0) {
    Start-Sleep -Seconds $BiosDelaySeconds
}
$sequenceStartedAt = [DateTime]::UtcNow
for ($sequenceIndex = 0; $sequenceIndex -lt $KeySequence.Count;
     $sequenceIndex++) {
    $step = $KeySequence[$sequenceIndex]
    if ($step -notmatch '^([A-Z])-([1-9][0-9]*)$') {
        throw "Invalid timed key step '${step}'. Expected KEY-delaySeconds, for example A-3."
    }
    $key = $Matches[1]
    $delaySeconds = [int]$Matches[2]
    Start-Sleep -Seconds $delaySeconds
    $process.Refresh()
    if ($process.HasExited) {
        throw "xemu exited before timed input step $($sequenceIndex + 1)."
    }
    $virtualKey = [int][char]$key
    & $SendKeyTool -ProcessId $ProcessId -VirtualKey $virtualKey
    $pressedAt = [DateTime]::UtcNow
    [ordered]@{
        schema_version = 1
        type = 'key_press'
        index = $sequenceIndex + 1
        key = $key
        virtual_key = $virtualKey
        preceding_delay_seconds = $delaySeconds
        sequence_elapsed_seconds = (
            $pressedAt - $sequenceStartedAt
        ).TotalSeconds
        process_elapsed_seconds = ($pressedAt - $startedAt).TotalSeconds
        pressed_at_utc = $pressedAt.ToString('o')
    } | ConvertTo-Json -Compress |
        Add-Content -LiteralPath $OutputPath -Encoding utf8
}

[pscustomobject]@{
    ProcessId = $ProcessId
    BiosDelaySeconds = $BiosDelaySeconds
    KeySequence = $KeySequence
    InputLog = $OutputPath
    CompletedAtUtc = [DateTime]::UtcNow.ToString('o')
}
