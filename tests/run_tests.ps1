# =====================================================================
# tests/run_tests.ps1 — Script tự động chuẩn bị Docker & chạy kiểm thử ZTA
# Cách dùng trên Windows PowerShell:
#   .\tests\run_tests.ps1              # Chạy toàn bộ KB0 -> KB4
#   .\tests\run_tests.ps1 kb1          # Chỉ chạy riêng KB1 (hoặc kb2, kb3, kb4)
#   .\tests\run_tests.ps1 --skip-kb4   # Chạy KB0 -> KB3 (không ngắt mạng catalog)
# =====================================================================

param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$TestArgs
)

$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host "   ZERO TRUST & MICRO-SEGMENTATION — AUTOMATED TEST RUNNER    " -ForegroundColor Cyan
Write-Host "==============================================================" -ForegroundColor Cyan

# 1. Kiểm tra Docker Engine đã chạy chưa
Write-Host "`n[1/3] Kiểm tra trạng thái Docker Desktop..." -ForegroundColor Yellow
docker info --format "{{.ServerVersion}}" > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host " Docker Desktop chưa chạy! Vui lòng bật Docker Desktop đợi Engine running rồi thử lại." -ForegroundColor Red
    exit 1
}
Write-Host " Docker Engine đang hoạt động." -ForegroundColor Green

# 2. Kiểm tra cụm 5 containers đã chạy chưa
Write-Host "`n[2/3] Kiểm tra cụm 5 containers (mysql-db, auth, catalog, order, nginx)..." -ForegroundColor Yellow
$RunningCount = (docker ps --filter "name=mysql-db" --filter "name=auth-service" --filter "name=catalog-service" --filter "name=order-service" --filter "name=nginx-gateway" -q | Measure-Object).Count

if ($RunningCount -lt 5) {
    Write-Host " Chưa đủ 5 containers đang chạy (hiện có $RunningCount/5). Đang khởi động docker-compose..." -ForegroundColor Yellow
    if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
        docker-compose up -d --build
    } else {
        docker compose up -d --build
    }
}

# Đợi mysql-db đạt trạng thái healthy
Write-Host " Đang kiểm tra trạng thái sẵn sàng của mysql-db..." -ForegroundColor Gray
for ($i = 0; $i -lt 20; $i++) {
    $Health = docker inspect --format "{{.State.Health.Status}}" mysql-db 2>$null
    if ($Health -eq "healthy") {
        Write-Host " Cả 5 containers và mysql-db (healthy) đã sẵn sàng!" -ForegroundColor Green
        break
    }
    Start-Sleep -Seconds 2
}

# 3. Chạy kịch bản kiểm thử Python
Write-Host "`n[3/3] Thực thi bộ kịch bản kiểm thử (tests/run_scenarios.py)..." -ForegroundColor Yellow
python "$PSScriptRoot\run_scenarios.py" @TestArgs
$ExitCode = $LASTEXITCODE

# Hiển thị file báo cáo mới nhất
$LatestReport = Get-ChildItem -Path "$PSScriptRoot\results\report_*.md" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($LatestReport) {
    Write-Host "`n📄 File báo cáo Markdown vừa xuất: $($LatestReport.FullName)" -ForegroundColor Cyan
}

exit $ExitCode

