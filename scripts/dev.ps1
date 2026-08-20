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
if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe") -or -not (Test-Path -LiteralPath "frontend\node_modules")) {
    throw "Run install.bat first."
}
$Backend = Start-Process -FilePath ".venv\Scripts\python.exe" -ArgumentList @("-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8765", "--ws-max-size", "1024", "--ws-max-queue", "8", "--reload") -WorkingDirectory $ProjectRoot -WindowStyle Hidden -PassThru
$Frontend = Start-Process -FilePath "npm.cmd" -ArgumentList @("run", "dev") -WorkingDirectory (Join-Path $ProjectRoot "frontend") -WindowStyle Hidden -PassThru
[System.IO.File]::WriteAllText((Join-Path $DataDir "dev-backend.pid"), [string]$Backend.Id)
[System.IO.File]::WriteAllText((Join-Path $DataDir "dev-frontend.pid"), [string]$Frontend.Id)
Write-Host "DEV_STATUS=PASS backend=http://127.0.0.1:8765 frontend=http://127.0.0.1:5173"
