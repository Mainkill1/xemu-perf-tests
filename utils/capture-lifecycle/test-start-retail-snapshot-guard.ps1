$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Assert-True {
    param([bool]$Condition, [string]$Message)

    if (-not $Condition) {
        throw "Assertion failed: $Message"
    }
}

$launcher = Join-Path $PSScriptRoot 'start-retail-snapshot.ps1'
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    $launcher, [ref]$tokens, [ref]$parseErrors)
Assert-True ($parseErrors.Count -eq 0) 'launcher parses without errors'

$commands = @($ast.FindAll({
            param($node)
            $node -is [System.Management.Automation.Language.CommandAst]
        }, $true))
Assert-True (@($commands | Where-Object {
            $_.GetCommandName() -eq 'Stop-Process'
        }).Count -eq 0) 'launcher contains no broad process termination'

$source = [System.IO.File]::ReadAllText($launcher)
$queryOffset = $source.IndexOf('Get-Process -Name xemu')
$guardOffset = $source.IndexOf('$existingXemu.Count -ne 0')
$launchOffset = $source.IndexOf('Start-Process @startParameters')
Assert-True ($queryOffset -ge 0) 'launcher queries xemu processes'
Assert-True ($guardOffset -gt $queryOffset) 'idle guard follows the process query'
Assert-True ($launchOffset -gt $guardOffset) 'idle guard precedes process launch'
Assert-True ($source.Contains("'launch-artifacts'")) `
    'ConfigPath derives launch-local artifacts'
Assert-True ($source.Contains('$process.Kill()')) `
    'post-launch failure attempts owned process cleanup'

$root = Join-Path ([System.IO.Path]::GetTempPath()) (
    'retail-launcher-' + [guid]::NewGuid().ToString('N'))
$syntheticProcess = $null
try {
    New-Item -ItemType Directory -Path $root | Out-Null
    $syntheticXemu = Join-Path $root 'xemu.exe'
    Copy-Item -LiteralPath $env:ComSpec -Destination $syntheticXemu
    $syntheticProcess = Start-Process -FilePath $syntheticXemu `
        -ArgumentList @('/d', '/c', 'ping -n 30 127.0.0.1 >nul') -PassThru
    Start-Sleep -Milliseconds 250
    Assert-True (-not $syntheticProcess.HasExited) `
        'owned synthetic xemu conflict remains live'

    $rejected = $false
    $rejectionMessage = $null
    try {
        & $launcher -Xemu 'unused-synthetic-xemu.exe'
    } catch {
        $rejectionMessage = $_.Exception.Message
        $rejected = $rejectionMessage -like `
            'Refusing to launch while * xemu process(es) exist.'
    }
    Assert-True $rejected (
        "foreign xemu process is rejected; actual='$rejectionMessage'")
} finally {
    if ($syntheticProcess -and -not $syntheticProcess.HasExited) {
        $syntheticProcess.Kill()
        [void]$syntheticProcess.WaitForExit(30000)
    }
}

$config = Join-Path $root 'xemu.toml'
$script:FakeProcess = [pscustomobject]@{
    Id = 4343
    HasExited = $false
    Killed = $false
}
$script:FakeProcess | Add-Member -MemberType ScriptMethod -Name Kill -Value {
    $this.Killed = $true
    $this.HasExited = $true
}
$script:FakeProcess | Add-Member -MemberType ScriptMethod -Name WaitForExit -Value {
    param([int]$Milliseconds)
    return $true
}
$script:FakeProcess | Add-Member -MemberType ScriptMethod -Name Refresh -Value { }
function Start-Process {
    param(
        [string]$FilePath,
        [object[]]$ArgumentList,
        [string]$RedirectStandardOutput,
        [string]$RedirectStandardError,
        [switch]$PassThru
    )
    return $script:FakeProcess
}
function Add-Type {
    param([string]$AssemblyName)
    throw 'injected post-launch failure'
}

try {
    [System.IO.File]::WriteAllText(
        $config, "[input.bindings]`nport1 = 'keyboard'`n")
    $postLaunchRejected = $false
    try {
        & $launcher -Xemu 'synthetic-xemu.exe' -ConfigPath $config
    } catch {
        $postLaunchRejected = $_.Exception.Message -eq `
            'injected post-launch failure'
    }
    Assert-True $postLaunchRejected 'post-launch failure remains observable'
    Assert-True $script:FakeProcess.Killed `
        'post-launch failure cleans owned process'
    Assert-True ((Test-Path -LiteralPath (
                Join-Path $root 'launch-artifacts') -PathType Container)) `
        'launcher writes logs under the run-local config directory'
} finally {
    if (Test-Path -LiteralPath $root) {
        Remove-Item -LiteralPath $root -Recurse -Force
    }
}

Write-Output 'start-retail-snapshot guard controls passed'
