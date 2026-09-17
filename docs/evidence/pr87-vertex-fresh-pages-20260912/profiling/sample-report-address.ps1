param([Parameter(Mandatory)][string]$RunRoot, [int]$Port = 16653)
$ErrorActionPreference = 'Stop'
$ready = $false
for ($attempt = 0; $attempt -lt 160; $attempt++) {
    $actionsPath = Join-Path $RunRoot 'actions.jsonl'
    if (Test-Path $actionsPath) {
        try { $ready = [bool](Get-Content $actionsPath | Select-String '"action":"Key"' | Select-Object -First 1) }
        catch { $ready = $false }
    }
    if ($ready) { break }
    Start-Sleep -Milliseconds 250
}
if (-not $ready) { throw 'First gameplay input not observed' }
$client = [Net.Sockets.TcpClient]::new()
$client.ReceiveTimeout = 10000
$client.SendTimeout = 10000
try {
    $client.Connect('127.0.0.1', $Port)
    $stream = $client.GetStream()
    $reader = [IO.StreamReader]::new($stream)
    $writer = [IO.StreamWriter]::new($stream, [Text.UTF8Encoding]::new($false))
    $writer.AutoFlush = $true
    [void]$reader.ReadLine()
    function Invoke-Qmp([hashtable]$Request) {
        $writer.WriteLine(($Request | ConvertTo-Json -Compress -Depth 5))
        do {
            $line = $reader.ReadLine()
            if ($null -eq $line) { throw 'QMP EOF' }
            $response = $line | ConvertFrom-Json -AsHashtable
        } while ($response['id'] -ne $Request['id'])
        if ($response.ContainsKey('error')) { throw ($response['error'] | ConvertTo-Json -Compress) }
        return $response['return']
    }
    function Hmp([string]$Command, [string]$Id) {
        Invoke-Qmp @{execute='human-monitor-command'; arguments=@{'command-line'=$Command}; id=$Id}
    }
    function Read-Word([uint64]$Address, [string]$Id) {
        $out = Hmp ('x/1xw 0x{0:x}' -f $Address) $Id
        $match = [regex]::Match([string]$out, '(?i):\s*0x([0-9a-f]{1,8})')
        if (-not $match.Success) { throw ('Unparsed guest word at 0x{0:x}: {1}' -f $Address, $out) }
        return [Convert]::ToUInt64($match.Groups[1].Value, 16)
    }
    [void](Invoke-Qmp @{execute='qmp_capabilities'; id='cap'})
    foreach ($eventName in @('nv2a_pgraph_vk_report_queued','nv2a_pgraph_vk_report_stall','nv2a_pgraph_report_written')) {
        [void](Invoke-Qmp @{execute='trace-event-set-state'; arguments=@{name=$eventName; enable=$true}; id=$eventName})
    }
    Start-Sleep -Seconds 4
    $samples = [Collections.Generic.List[object]]::new()
    for ($i=0; $i -lt 180; $i++) {
        $at = [DateTime]::UtcNow.ToString('o')
        $text = Hmp 'info registers' "regs-$i"
        $eipMatch = [regex]::Match([string]$text, '(?i)\bEIP\s*=\s*([0-9a-f]{8})')
        $espMatch = [regex]::Match([string]$text, '(?i)\bESP\s*=\s*([0-9a-f]{8})')
        $eip = if ($eipMatch.Success) { $eipMatch.Groups[1].Value.ToLowerInvariant() } else { $null }
        $entry = [ordered]@{at_utc=$at; eip=$eip; record_gva=$null; record_gpa=$null; done=$null; index=$null; error=$null}
        if ($eip -in @('00336940','000b2492')) {
            try {
                $index = [uint64]0
                if ($eip -eq '00336940') {
                    if (-not $espMatch.Success) { throw 'No ESP in register sample' }
                    $esp = [Convert]::ToUInt64($espMatch.Groups[1].Value,16)
                    $index = Read-Word ($esp + 4) "index-$i"
                }
                $guestContext = Read-Word 0x348d78 "context-$i"
                $basePtr = Read-Word ($guestContext + 0x7d4 + (($index -shr 8) * 4)) "base-$i"
                $recordGva = [uint64]($basePtr + (($index -band 255) * 16))
                $translation = Hmp ('gva2gpa 0x{0:x}' -f $recordGva) "translate-$i"
                $gpaMatch = [regex]::Match([string]$translation, '(?i)gpa:\s*0x([0-9a-f]+)')
                if (-not $gpaMatch.Success) { throw ('Unmapped guest record: ' + $translation) }
                $done = Read-Word ($recordGva + 12) "done-$i"
                $entry.index = $index
                $entry.record_gva = ('0x{0:x}' -f $recordGva)
                $entry.record_gpa = ('0x{0:x}' -f [Convert]::ToUInt64($gpaMatch.Groups[1].Value,16))
                $entry.done = ('0x{0:x8}' -f $done)
            } catch { $entry.error = $_.Exception.Message }
        }
        $samples.Add([pscustomobject]$entry)
        Start-Sleep -Milliseconds 20
    }
    $output = Join-Path $RunRoot 'guest-report-address-samples.json'
    $samples | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $output -Encoding utf8
    $hits = @($samples | Where-Object { $_.record_gpa })
    [pscustomobject]@{samples=$samples.Count; resolved=$hits.Count; gpas=@($hits | Group-Object record_gpa | Sort-Object Count -Descending | Select-Object -First 5 Name,Count); errors=@($samples | Where-Object error | Group-Object error | Select-Object -First 5 Name,Count)} | ConvertTo-Json -Compress -Depth 5
} finally {
    $client.Dispose()
}
