# UTF-8 PowerShell Script for LOGSCO Service
param(
    [string]$Action = "start"
)

# Set UTF-8 encoding
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "    LOGSCO Anomaly Detection Service" -ForegroundColor Yellow
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host

if ($Action -eq "start") {
    Write-Host "[1/4] Checking Docker..." -ForegroundColor Green
    try {
        docker --version | Out-Null
        Write-Host "Docker is available" -ForegroundColor Green
    }
    catch {
        Write-Host "ERROR: Docker is not running" -ForegroundColor Red
        Write-Host "Please start Docker Desktop and try again" -ForegroundColor Yellow
        Read-Host "Press Enter to exit"
        exit 1
    }

    Write-Host "[2/4] Loading Docker image..." -ForegroundColor Green
    if (Test-Path "anomalytoolkit.tar") {
        docker load -i anomalytoolkit.tar
    }
    else {
        Write-Host "Image file not found, using existing image..." -ForegroundColor Yellow
    }

    Write-Host "[3/4] Environment setup..." -ForegroundColor Green
    if (-not (Test-Path ".env")) {
        Copy-Item ".env.example" ".env"
        Write-Host "Environment file created" -ForegroundColor Green
    }

    Write-Host "[4/4] Starting service..." -ForegroundColor Green
    docker-compose up -d

    Write-Host
    Write-Host "SUCCESS: Service started!" -ForegroundColor Green
    Write-Host
    Write-Host "Access URLs:" -ForegroundColor Cyan
    Write-Host "  Main: http://localhost:8000" -ForegroundColor White
    Write-Host "  Dashboard: http://localhost:8000/dashboard/" -ForegroundColor White
    Write-Host "  Upload: http://localhost:8000/upload/" -ForegroundColor White
    Write-Host
    Write-Host "To stop: .\service.ps1 stop" -ForegroundColor Yellow
}
elseif ($Action -eq "stop") {
    Write-Host "Stopping service..." -ForegroundColor Yellow
    docker-compose down
    Write-Host "Service stopped successfully!" -ForegroundColor Green
}

Write-Host
Read-Host "Press Enter to continue"