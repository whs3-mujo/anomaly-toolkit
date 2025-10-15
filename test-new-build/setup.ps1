# PowerShell ?ㅽ겕由쏀듃 - setup.ps1
Write-Host "LOGSCO ?댁긽 濡쒓렇 ?먯? ?쒕퉬???ㅼ젙 以?.." -ForegroundColor Green

# ?섍꼍 蹂???뚯씪 ?앹꽦
if (-not (Test-Path -Path ".env")) {
    Write-Host "?섍꼍 蹂???뚯씪 ?앹꽦 以?.." -ForegroundColor Yellow
    Copy-Item -Path ".env.example" -Destination ".env"
    
    # SECRET_KEY ?먮룞 ?앹꽦
    $secretKey = -join ((65..90) + (97..122) + (48..57) + 33,35,37,38,40,41,42,43,45,46,47,58,59,61,63,64,91,93,94,95,123,125,126 | Get-Random -Count 50 | ForEach-Object {[char]$_})
    (Get-Content ".env") -replace "SECRET_KEY=.*", "SECRET_KEY=$secretKey" | Set-Content ".env"
    Write-Host "?덈줈??SECRET_KEY媛 ?앹꽦?섏뿀?듬땲??" -ForegroundColor Green
}

# ?꾩빱 ?대?吏 濡쒕뱶
Write-Host "?꾩빱 ?대?吏 濡쒕뵫 以?.. (?좎떆 ?쒓컙???뚯슂?????덉뒿?덈떎)" -ForegroundColor Yellow
docker load -i anomalytoolkit.tar

Write-Host "?ㅼ젙 ?꾨즺! ?ㅼ쓬 紐낅졊?대줈 ?쒕퉬?ㅻ? ?쒖옉?섏꽭??" -ForegroundColor Green
Write-Host "docker-compose up -d" -ForegroundColor Cyan
Write-Host "釉뚮씪?곗??먯꽌 http://localhost:8000/dashboard 濡??묒냽?섏꽭??" -ForegroundColor Cyan
