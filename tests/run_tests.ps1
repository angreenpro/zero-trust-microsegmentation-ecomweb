# =====================================================================
# tests/run_tests.ps1 - Automated Zero Trust & Micro-segmentation Test Runner
# Usage in Windows PowerShell:
#   .\tests\run_tests.ps1              # Run all scenarios (KB0 -> KB4)
#   .\tests\run_tests.ps1 kb1          # Run only KB1 (or kb2, kb3, kb4)
#   .\tests\run_tests.ps1 --skip-kb4   # Run KB0 -> KB3 (skip catalog isolation)
# =====================================================================

param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$TestArgs
)

$ErrorActionPreference = "Continue"
chcp 65001 > $null
[Console]::InputEncoding  = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding           = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING     = "utf-8"
$env:PYTHONUTF8           = "1"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host "   ZERO TRUST & MICRO-SEGMENTATION - AUTOMATED TEST RUNNER    " -ForegroundColor Cyan
Write-Host "==============================================================" -ForegroundColor Cyan

# 1. Check Docker Engine status
Write-Host "`n[1/3] Checking Docker Desktop status..." -ForegroundColor Yellow
docker info --format "{{.ServerVersion}}" > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [FAIL] Docker Desktop is not running! Please start Docker Desktop first." -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] Docker Engine is running." -ForegroundColor Green

# 2. Check all 5 containers
Write-Host "`n[2/3] Checking 5 containers (mysql-db, auth, catalog, order, nginx)..." -ForegroundColor Yellow
$RunningCount = (docker ps --filter "name=mysql-db" --filter "name=auth-service" --filter "name=catalog-service" --filter "name=order-service" --filter "name=nginx-gateway" -q | Measure-Object).Count

if ($RunningCount -lt 5) {
    Write-Host "  [WARN] Only $RunningCount/5 containers running. Starting docker-compose..." -ForegroundColor Yellow
    if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
        docker-compose up -d --build
    } else {
        docker compose up -d --build
    }
}

Write-Host "  [WAIT] Waiting for mysql-db healthcheck..." -ForegroundColor Gray
for ($i = 0; $i -lt 20; $i++) {
    $Health = docker inspect --format "{{.State.Health.Status}}" mysql-db 2>$null
    if ($Health -eq "healthy") {
        Write-Host "  [OK] All 5 containers and mysql-db (healthy) are ready!" -ForegroundColor Green
        break
    }
    Start-Sleep -Seconds 2
}

# 3. Run Python scenario test suite
Write-Host "`n[3/3] Running test scenarios (tests/run_scenarios.py)..." -ForegroundColor Yellow
python "$PSScriptRoot\run_scenarios.py" @TestArgs
$ExitCode = $LASTEXITCODE

# Print latest Markdown report path
$LatestReport = Get-ChildItem -Path "$PSScriptRoot\results\report_*.md" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($LatestReport) {
    Write-Host "`n[REPORT] Markdown report saved to: $($LatestReport.FullName)" -ForegroundColor Cyan
}

exit $ExitCode
