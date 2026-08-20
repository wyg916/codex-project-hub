$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $ProjectRoot
$ConfiguredDataDir = if ([string]::IsNullOrWhiteSpace($env:CPC_DATA_DIR)) { Join-Path $ProjectRoot "data" } else { $env:CPC_DATA_DIR }
$DataDir = [System.IO.Path]::GetFullPath($ConfiguredDataDir)
if ($DataDir.StartsWith("\\") -or $DataDir.TrimEnd("\") -eq [System.IO.Path]::GetPathRoot($DataDir).TrimEnd("\")) {
    throw "CPC_DATA_DIR must be a local, non-root directory."
}
if (Test-Path -LiteralPath $DataDir) {
    $DataItem = Get-Item -LiteralPath $DataDir -Force
    if (-not $DataItem.PSIsContainer -or ($DataItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
        throw "CPC_DATA_DIR must be a real directory, not a file or reparse point."
    }
}
$PidFile = Join-Path $DataDir "server.pid"
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$StartLockPath = Join-Path $DataDir "server.start.lock"
$ServerArgumentsText = "-m uvicorn backend.app.main:app --host 127.0.0.1 --port 8765 --ws-max-size 1024 --ws-max-queue 8"

if (-not (Test-Path -LiteralPath $DataDir)) {
    Write-Host "STOP_STATUS=PASS (no managed process)"
    exit 0
}

if (Test-Path -LiteralPath $StartLockPath) {
    $StartLockItem = Get-Item -LiteralPath $StartLockPath -Force
    if ($StartLockItem.PSIsContainer -or ($StartLockItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
        throw "The server management lock path is unsafe."
    }
}
try {
    $StartLock = [System.IO.File]::Open(
        $StartLockPath,
        [System.IO.FileMode]::OpenOrCreate,
        [System.IO.FileAccess]::ReadWrite,
        [System.IO.FileShare]::None
    )
} catch {
    Write-Error "A start or stop operation is already in progress for this data directory."
    exit 1
}

if (-not (Test-Path -LiteralPath $PidFile)) {
    Write-Host "STOP_STATUS=PASS (no managed process)"
    exit 0
}

function Test-ExactServerCommand {
    param(
        [Parameter(Mandatory = $true)] $ProcessInfo,
        [string] $RequiredExecutable = ""
    )
    if (-not $ProcessInfo -or -not $ProcessInfo.ExecutablePath -or -not $ProcessInfo.CommandLine) {
        return $false
    }
    try {
        $ActualExecutable = [System.IO.Path]::GetFullPath([string]$ProcessInfo.ExecutablePath)
    } catch {
        return $false
    }
    if ($RequiredExecutable) {
        if ($ActualExecutable -ne [System.IO.Path]::GetFullPath($RequiredExecutable)) { return $false }
    } elseif ([System.IO.Path]::GetFileName($ActualExecutable) -ne "python.exe") {
        return $false
    }
    $Command = ([string]$ProcessInfo.CommandLine).Trim()
    foreach ($Prefix in @((('"' + $ActualExecutable + '" ')), ($ActualExecutable + ' '))) {
        if ($Command.StartsWith($Prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $Command.Substring($Prefix.Length) -ceq $ServerArgumentsText
        }
    }
    return $false
}

function Test-ControlledServerProcess {
    param([Parameter(Mandatory = $true)] $ListenerProcess)
    if (-not (Test-ExactServerCommand $ListenerProcess)) { return $false }
    $LauncherPid = [int]$ListenerProcess.ParentProcessId
    if ($LauncherPid -le 0) { return $false }
    $Launcher = Get-CimInstance Win32_Process -Filter "ProcessId = $LauncherPid" -ErrorAction SilentlyContinue
    return [bool]($Launcher -and (Test-ExactServerCommand $Launcher $Python))
}

$PidText = (Get-Content -LiteralPath $PidFile -Raw).Trim()
if ($PidText -notmatch "^\d+$") {
    Remove-Item -LiteralPath $PidFile -Force
    Write-Host "STOP_STATUS=PASS (invalid stale pid file removed)"
    exit 0
}

$ManagedPid = [int]$PidText
$Managed = Get-CimInstance Win32_Process -Filter "ProcessId = $ManagedPid" -ErrorAction SilentlyContinue
if (-not $Managed) {
    Remove-Item -LiteralPath $PidFile -Force
    Write-Host "STOP_STATUS=PASS (stale pid file removed)"
    exit 0
}

$IsOwned = Test-ControlledServerProcess $Managed
$Listeners = @(Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue)
$IsOwned = $IsOwned -and $Listeners.Count -eq 1 -and [int]$Listeners[0].OwningProcess -eq $ManagedPid
if (-not $IsOwned) {
    Remove-Item -LiteralPath $PidFile -Force
    Write-Host "STOP_STATUS=PASS (pid reused by unrelated process; process preserved)"
    exit 0
}

Stop-Process -Id $ManagedPid -Force -ErrorAction SilentlyContinue

Remove-Item -LiteralPath $PidFile -Force
Write-Host "STOP_STATUS=PASS stopped=1"
