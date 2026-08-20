$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $ProjectRoot
$env:PYTHONUTF8 = "1"
if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) { throw "Run install.bat first." }

& ".venv\Scripts\python.exe" scripts\verify-python-lock.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& ".venv\Scripts\python.exe" -m pip check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& ".venv\Scripts\python.exe" -m pip_audit --local --strict --progress-spinner off
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& ".venv\Scripts\python.exe" -m pytest backend\tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Push-Location frontend
try {
    npm.cmd run test
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    npm.cmd run e2e
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}
& ".venv\Scripts\python.exe" scripts\update-codex-status.py --help | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& ".venv\Scripts\python.exe" scripts\create-demo-repo.py --help | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "TEST_ALL_STATUS=PASS"
