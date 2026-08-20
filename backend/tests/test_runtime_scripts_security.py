from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def test_start_and_stop_share_data_dir_and_strict_process_identity() -> None:
    start = (ROOT / "scripts" / "start.ps1").read_text(encoding="utf-8")
    stop = (ROOT / "scripts" / "stop.ps1").read_text(encoding="utf-8")
    for script in (start, stop):
        assert "CPC_DATA_DIR" in script
        assert 'Join-Path $DataDir "server.pid"' in script
        assert "--host 127.0.0.1 --port 8765" in script
        assert script.index("Set-Location -LiteralPath $ProjectRoot") < script.index(
            "[System.IO.Path]::GetFullPath($ConfiguredDataDir)"
        )
    assert "$Tree" not in stop
    assert "Stop-Process -Id $ManagedPid" in stop
    assert "Get-ControlledListenerForLauncher $Process.Id" in start
    assert "[System.IO.File]::WriteAllText($PidFile, [string]$ManagedServer.ProcessId)" in start
    assert "WriteAllText($PidFile, [string]$Process.Id)" not in start
    assert "Test-ControlledServerProcess" in start and "Test-ControlledServerProcess" in stop
    assert "ParentProcessId" in start and "ParentProcessId" in stop
    assert "[System.IO.FileShare]::None" in start and "[System.IO.FileShare]::None" in stop
    assert "$ServerArgumentsText" in start and "$ServerArgumentsText" in stop


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell process ownership regression is Windows-specific")
def test_stop_preserves_managed_process_child_sentinel(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    stop_script = ROOT / "scripts" / "stop.ps1"
    python = ROOT / ".venv" / "Scripts" / "python.exe"
    harness = tmp_path / "stop-harness.ps1"

    def quote(value: Path) -> str:
        return str(value).replace("'", "''")

    harness.write_text(
        f"""
$ErrorActionPreference = 'Stop'
$env:CPC_DATA_DIR = '{quote(data_dir)}'
$global:ManagedPid = 424242
$global:LauncherPid = 424241
[System.IO.File]::WriteAllText((Join-Path $env:CPC_DATA_DIR 'server.pid'), [string]$global:ManagedPid)
$SentinelScript = Join-Path $env:CPC_DATA_DIR 'sentinel.py'
[System.IO.File]::WriteAllText($SentinelScript, 'import time; time.sleep(30)')
$global:Sentinel = Start-Process -FilePath '{quote(python)}' -ArgumentList @($SentinelScript) -WindowStyle Hidden -PassThru
$global:ManagedRecord = [pscustomobject]@{{ ProcessId = $global:ManagedPid; ParentProcessId = $global:LauncherPid; ExecutablePath = 'C:\BasePython\python.exe'; CommandLine = '"C:\BasePython\python.exe" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8765 --ws-max-size 1024 --ws-max-queue 8' }}
$global:LauncherRecord = [pscustomobject]@{{ ProcessId = $global:LauncherPid; ParentProcessId = 1; ExecutablePath = '{quote(python)}'; CommandLine = '"{quote(python)}" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8765 --ws-max-size 1024 --ws-max-queue 8' }}
$global:ChildRecord = [pscustomobject]@{{ ProcessId = $global:Sentinel.Id; ParentProcessId = $global:ManagedPid; ExecutablePath = '{quote(python)}'; CommandLine = 'sentinel' }}
$global:Stopped = @()
function global:Get-CimInstance {{
    param($ClassName, $Filter, $ErrorAction)
    if ($Filter -eq "ProcessId = $global:ManagedPid") {{ return $global:ManagedRecord }}
    if ($Filter -eq "ProcessId = $global:LauncherPid") {{ return $global:LauncherRecord }}
    if ($Filter -eq "ParentProcessId = $global:LauncherPid") {{ return $global:ManagedRecord }}
    return @($global:LauncherRecord, $global:ManagedRecord, $global:ChildRecord)
}}
function global:Get-NetTCPConnection {{
    param($LocalAddress, $LocalPort, $State, $ErrorAction)
    return [pscustomobject]@{{ OwningProcess = $global:ManagedPid }}
}}
function global:Stop-Process {{
    param([int]$Id, [switch]$Force, $ErrorAction)
    $global:Stopped += $Id
    if ($Id -eq $global:Sentinel.Id) {{ Microsoft.PowerShell.Management\Stop-Process -Id $Id -Force }}
}}
try {{
    & '{quote(stop_script)}'
    $global:Sentinel.Refresh()
    if ($global:Sentinel.HasExited) {{ throw 'child sentinel was terminated' }}
    if ($global:Stopped.Count -ne 1 -or $global:Stopped[0] -ne $global:ManagedPid) {{ throw 'unexpected process termination target' }}
}} finally {{
    Microsoft.PowerShell.Management\Stop-Process -Id $global:Sentinel.Id -Force -ErrorAction SilentlyContinue
}}
""",
        encoding="utf-8",
    )
    completed = subprocess.run(
        ["pwsh.exe", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(harness)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        shell=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell process ownership regression is Windows-specific")
def test_start_retries_transient_health_for_strictly_owned_listener(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    start_script = ROOT / "scripts" / "start.ps1"
    python = ROOT / ".venv" / "Scripts" / "python.exe"
    harness = tmp_path / "start-transient-harness.ps1"
    health_count = data_dir / "health-count.txt"

    def quote(value: Path) -> str:
        return str(value).replace("'", "''")

    harness.write_text(
        f"""
$ErrorActionPreference = 'Stop'
$env:CPC_DATA_DIR = '{quote(data_dir)}'
$env:CPC_NO_BROWSER = '1'
$global:ManagedPid = 424242
$global:LauncherPid = 424241
$global:HealthCalls = 0
$global:HealthCountPath = '{quote(health_count)}'
[System.IO.File]::WriteAllText((Join-Path $env:CPC_DATA_DIR 'server.pid'), [string]$global:ManagedPid)
$global:ManagedRecord = [pscustomobject]@{{ ProcessId = $global:ManagedPid; ParentProcessId = $global:LauncherPid; ExecutablePath = 'C:\BasePython\python.exe'; CommandLine = '"C:\BasePython\python.exe" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8765 --ws-max-size 1024 --ws-max-queue 8' }}
$global:LauncherRecord = [pscustomobject]@{{ ProcessId = $global:LauncherPid; ParentProcessId = 1; ExecutablePath = '{quote(python)}'; CommandLine = '"{quote(python)}" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8765 --ws-max-size 1024 --ws-max-queue 8' }}
function global:Get-CimInstance {{
    param($ClassName, $Filter, $ErrorAction)
    if ($Filter -eq "ProcessId = $global:ManagedPid") {{ return $global:ManagedRecord }}
    if ($Filter -eq "ProcessId = $global:LauncherPid") {{ return $global:LauncherRecord }}
    return $null
}}
function global:Get-NetTCPConnection {{
    param($LocalAddress, $LocalPort, $State, $ErrorAction)
    return [pscustomobject]@{{ OwningProcess = $global:ManagedPid }}
}}
function global:Invoke-RestMethod {{
    param($Uri, $TimeoutSec)
    $global:HealthCalls += 1
    [System.IO.File]::WriteAllText($global:HealthCountPath, [string]$global:HealthCalls)
    if ($global:HealthCalls -eq 1) {{ throw 'transient health failure' }}
    return [pscustomobject]@{{ status = 'ok'; service = 'codex-project-hub'; version = '0.1.0' }}
}}
function global:Start-Sleep {{ param($Milliseconds) }}
function global:Start-Process {{ throw 'a new process must not be started for an owned listener' }}
& '{quote(start_script)}'
""",
        encoding="utf-8",
    )
    completed = subprocess.run(
        ["pwsh.exe", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(harness)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        shell=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert "START_STATUS=PASS (existing healthy instance)" in completed.stdout
    assert health_count.read_text(encoding="utf-8") == "2"


def test_install_fails_closed_on_runtime_and_lock_requirements() -> None:
    install = (ROOT / "scripts" / "install.ps1").read_text(encoding="utf-8")
    assert "requires ^20.19.0 or >=22.12.0" in install
    assert "requires Python 3.11" in install
    assert "requires 64-bit x86_64/AMD64 Windows" in install
    assert "--require-hashes -r backend\\requirements-bootstrap.txt" in install
    assert "-r backend\\pylock.toml" in install
    assert "frontend/package-lock.json is required" in install
    assert "npm.cmd ci" in install
    assert "playwright install chromium" in install
    assert '".venv\Scripts\python.exe" -m pip check' in install
