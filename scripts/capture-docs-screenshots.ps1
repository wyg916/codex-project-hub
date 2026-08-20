$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$FrontendRoot = Join-Path $ProjectRoot "frontend"

Push-Location -LiteralPath $FrontendRoot
try {
    $env:CPC_CAPTURE_DOCS = "1"
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
    npm.cmd exec -- playwright test e2e/docs-screenshots.spec.ts
    if ($LASTEXITCODE -ne 0) { throw "Documentation screenshot capture failed" }
} finally {
    Remove-Item Env:CPC_CAPTURE_DOCS -ErrorAction SilentlyContinue
    Pop-Location
}

Write-Host "DOCS_SCREENSHOTS_STATUS=PASS"
