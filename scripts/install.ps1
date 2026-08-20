$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $ProjectRoot

foreach ($Command in @("git", "node", "npm.cmd", "py")) {
    if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) {
        throw "Missing required command: $Command"
    }
}

$NodeVersionText = (& node -p "process.versions.node").Trim()
if ($LASTEXITCODE -ne 0 -or $NodeVersionText -notmatch '^(\d+)\.(\d+)\.(\d+)$') {
    throw "Unable to determine the Node.js version."
}
$NodeMajor = [int]$Matches[1]
$NodeMinor = [int]$Matches[2]
$NodeSupported = ($NodeMajor -eq 20 -and $NodeMinor -ge 19) -or
    ($NodeMajor -eq 22 -and $NodeMinor -ge 12) -or
    ($NodeMajor -gt 22)
if (-not $NodeSupported) {
    throw "Unsupported Node.js $NodeVersionText. Codex Project Hub requires ^20.19.0 or >=22.12.0."
}

if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) {
    py -3.11 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Python virtual environment creation failed" }
}
$PythonVersion = (& ".venv\Scripts\python.exe" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
if ($LASTEXITCODE -ne 0 -or $PythonVersion -ne "3.11") {
    throw "Unsupported Python $PythonVersion. Codex Project Hub requires Python 3.11."
}
$PythonPlatform = (& ".venv\Scripts\python.exe" -c "import platform, struct; print(platform.machine() + '|' + str(struct.calcsize('P') * 8))").Trim()
if ($LASTEXITCODE -ne 0 -or $PythonPlatform -notmatch "^(AMD64|x86_64)\|64$") {
    throw "Unsupported Python platform $PythonPlatform. backend/pylock.toml requires 64-bit x86_64/AMD64 Windows."
}
& ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --require-hashes -r backend\requirements-bootstrap.txt
if ($LASTEXITCODE -ne 0) { throw "Python packaging toolchain installation failed" }
& ".venv\Scripts\python.exe" scripts\verify-python-lock.py
if ($LASTEXITCODE -ne 0) { throw "Python dependency lock verification failed" }
& ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --index-url https://pypi.org/simple -r backend\pylock.toml
if ($LASTEXITCODE -ne 0) { throw "Python dependency installation failed" }

Push-Location frontend
try {
    if (-not (Test-Path -LiteralPath "package-lock.json")) {
        throw "frontend/package-lock.json is required for deterministic installation."
    }
    npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed" }
    npm.cmd exec -- playwright install chromium
    if ($LASTEXITCODE -ne 0) { throw "Playwright Chromium installation failed" }
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
} finally {
    Pop-Location
}

& ".venv\Scripts\python.exe" -m pip check
if ($LASTEXITCODE -ne 0) { throw "Python dependency consistency check failed" }
& ".venv\Scripts\python.exe" -c "from backend.app.config import get_settings; from backend.app.db.database import Database; Database(get_settings().database_path); print('SQLite initialized')"
if ($LASTEXITCODE -ne 0) { throw "SQLite initialization failed" }
Write-Host "INSTALL_STATUS=PASS"
