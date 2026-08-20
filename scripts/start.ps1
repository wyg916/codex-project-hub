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
} else {
    New-Item -ItemType Directory -Path $DataDir | Out-Null
}
$env:CPC_DATA_DIR = $DataDir
$Url = "http://127.0.0.1:8765"
$HealthUrl = "$Url/api/health"
$PidFile = Join-Path $DataDir "server.pid"
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$DefaultProjects = Join-Path $ProjectRoot "config\default-projects.json"
$StartLockPath = Join-Path $DataDir "server.start.lock"
$ServerArgumentsText = "-m uvicorn backend.app.main:app --host 127.0.0.1 --port 8765 --ws-max-size 1024 --ws-max-queue 8"

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
    Write-Error "Another start operation is already in progress for this data directory."
    exit 1
}

function Test-ControlCenterHealth {
    try {
        $Response = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 1
        return $Response.status -eq "ok" -and $Response.service -eq "codex-project-hub" -and $Response.version -eq "0.1.0"
    } catch {
        return $false
    }
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

function Get-OwnedServerProcess {
    if (-not (Test-Path -LiteralPath $PidFile)) { return $null }
    $PidText = (Get-Content -LiteralPath $PidFile -Raw).Trim()
    if ($PidText -notmatch "^\d+$") { return $null }
    $Managed = Get-CimInstance Win32_Process -Filter "ProcessId = $PidText" -ErrorAction SilentlyContinue
    if (-not $Managed -or -not (Test-ControlledServerProcess $Managed)) { return $null }
    $Listeners = @(Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue)
    if ($Listeners.Count -ne 1 -or [int]$Listeners[0].OwningProcess -ne [int]$Managed.ProcessId) {
        return $null
    }
    return $Managed
}

function Get-ControlledListenerForLauncher([int]$LauncherPid) {
    $Launcher = Get-CimInstance Win32_Process -Filter "ProcessId = $LauncherPid" -ErrorAction SilentlyContinue
    if (-not $Launcher -or -not (Test-ExactServerCommand $Launcher $Python)) { return $null }
    $Candidates = @(
        Get-CimInstance Win32_Process -Filter "ParentProcessId = $LauncherPid" -ErrorAction SilentlyContinue |
            Where-Object { Test-ExactServerCommand $_ }
    )
    if ($Candidates.Count -ne 1) { return $null }
    $Candidate = $Candidates[0]
    $Listeners = @(Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue)
    if ($Listeners.Count -ne 1 -or [int]$Listeners[0].OwningProcess -ne [int]$Candidate.ProcessId) {
        return $null
    }
    return $Candidate
}

$OwnedServer = Get-OwnedServerProcess
if ($OwnedServer) {
    for ($Attempt = 0; $Attempt -lt 10; $Attempt++) {
        $CurrentOwnedServer = Get-OwnedServerProcess
        if (-not $CurrentOwnedServer -or [int]$CurrentOwnedServer.ProcessId -ne [int]$OwnedServer.ProcessId) {
            throw "The managed Codex Project Hub process identity changed during its health check."
        }
        if (Test-ControlCenterHealth) {
            Write-Host "START_STATUS=PASS (existing healthy instance)"
            if ($env:CPC_NO_BROWSER -ne "1") { Start-Process $Url }
            exit 0
        }
        Start-Sleep -Milliseconds 250
    }
    throw "The managed Codex Project Hub instance owns port 8765 but did not become healthy."
}

if (-not (Test-Path -LiteralPath $Python) -or -not (Test-Path -LiteralPath "frontend\dist\index.html")) {
    Write-Error "Dependencies or frontend build are missing. Run install.bat first."
    exit 1
}

$UnownedHealth = Test-ControlCenterHealth
$PortOwner = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
if ($UnownedHealth -or $PortOwner) {
    throw "Port 8765 is occupied by a process that is not owned by this checkout."
}

& $Python -X utf8 "scripts\register-default-projects.py" --config $DefaultProjects
if ($LASTEXITCODE -ne 0) {
    Write-Error "Default project registration failed. Review the output above."
    exit 1
}

$PortOwner = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
if ($PortOwner) {
    throw "Port 8765 became occupied by a process that is not owned by this checkout."
}
if (Test-Path -LiteralPath $PidFile) { Remove-Item -LiteralPath $PidFile -Force }

$OutLog = Join-Path $DataDir "server.out.log"
$ErrLog = Join-Path $DataDir "server.err.log"
$Process = Start-Process -FilePath $Python `
    -ArgumentList @("-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8765", "--ws-max-size", "1024", "--ws-max-queue", "8") `
    -WorkingDirectory $ProjectRoot -WindowStyle Hidden -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog -PassThru

$ManagedServer = $null
for ($Attempt = 0; $Attempt -lt 60; $Attempt++) {
    $ManagedServer = Get-ControlledListenerForLauncher $Process.Id
    if ($ManagedServer -and (Test-ControlCenterHealth)) {
        [System.IO.File]::WriteAllText($PidFile, [string]$ManagedServer.ProcessId)
        Write-Host "START_STATUS=PASS PID=$($ManagedServer.ProcessId) LAUNCHER=$($Process.Id) URL=$Url"
        if ($env:CPC_NO_BROWSER -ne "1") { Start-Process $Url }
        exit 0
    }
    if ($Process.HasExited) { break }
    Start-Sleep -Milliseconds 250
}

if ($ManagedServer) { Stop-Process -Id $ManagedServer.ProcessId -Force -ErrorAction SilentlyContinue }
if (-not $Process.HasExited) { Stop-Process -Id $Process.Id -Force }
if (Test-Path -LiteralPath $PidFile) { Remove-Item -LiteralPath $PidFile -Force }
Write-Error "Health check failed. Review $ErrLog."
exit 1
