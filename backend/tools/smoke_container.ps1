# PowerShell 5.1 / Core Wrapper for Container Smoke Runner (D151)
param(
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"

Write-Host "=== ScamShield PowerShell Container Smoke Test ===" -ForegroundColor Cyan
Write-Host "Target URL: $BaseUrl"

$scriptPath = Join-Path $PSScriptRoot "smoke_container.py"
python $scriptPath $BaseUrl

if ($LASTEXITCODE -eq 0) {
    Write-Host "=== All Container Smoke Tests Passed Successfully! ===" -ForegroundColor Green
    exit 0
} else {
    Write-Host "=== Container Smoke Tests Failed! ===" -ForegroundColor Red
    exit 1
}
