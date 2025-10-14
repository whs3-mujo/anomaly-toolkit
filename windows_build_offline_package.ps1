# 인코딩 설정
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "LOGSCO 이상 로그 탐지 서비스 오프라인 패키지 빌드 시작..." -ForegroundColor Green

# 1. 도커 이미지 빌드
Write-Host "오프라인 환경용 도커 이미지 빌드 중..." -ForegroundColor Yellow
docker build -f Dockerfile.offline -t anomaly-toolkit:offline .

# 2. 도커 이미지를 tar 파일로 저장
Write-Host "도커 이미지 패키징 중..." -ForegroundColor Yellow
docker save -o anomalytoolkit.tar anomaly-toolkit:offline

# 3. 배포 패키지 폴더 생성
Write-Host "배포 패키지 생성 중..." -ForegroundColor Yellow
New-Item -Path "offline-package" -ItemType Directory -Force
Copy-Item -Path "docker-compose.offline.yml" -Destination "offline-package\docker-compose.yml"
Copy-Item -Path "anomalytoolkit.tar" -Destination "offline-package\"

# 빈 디렉터리만 생성 (테스트 데이터 포함하지 않음)
New-Item -Path "offline-package\media" -ItemType Directory -Force
New-Item -Path "offline-package\logs" -ItemType Directory -Force

Write-Host "패키지에서 테스트 데이터 제외됨 (깨끗한 설치)" -ForegroundColor Cyan

# 4. 환경 설정 파일 복사
Copy-Item -Path ".env.example" -Destination "offline-package\"

# 5. 배치 스크립트 및 PowerShell 스크립트 복사
Copy-Item -Path "start_service.bat" -Destination "offline-package\"
Copy-Item -Path "stop_service.bat" -Destination "offline-package\"
Copy-Item -Path "service.ps1" -Destination "offline-package\"

# 6. 설치 스크립트 생성
@"
# PowerShell 스크립트 - setup.ps1
Write-Host "LOGSCO 이상 로그 탐지 서비스 설정 중..." -ForegroundColor Green

# 환경 변수 파일 생성
if (-not (Test-Path -Path ".env")) {
    Write-Host "환경 변수 파일 생성 중..." -ForegroundColor Yellow
    Copy-Item -Path ".env.example" -Destination ".env"
    
    # SECRET_KEY 자동 생성
    `$secretKey = -join ((65..90) + (97..122) + (48..57) + 33,35,37,38,40,41,42,43,45,46,47,58,59,61,63,64,91,93,94,95,123,125,126 | Get-Random -Count 50 | ForEach-Object {[char]`$_})
    (Get-Content ".env") -replace "SECRET_KEY=.*", "SECRET_KEY=`$secretKey" | Set-Content ".env"
    Write-Host "새로운 SECRET_KEY가 생성되었습니다." -ForegroundColor Green
}

# 도커 이미지 로드
Write-Host "도커 이미지 로딩 중... (잠시 시간이 소요될 수 있습니다)" -ForegroundColor Yellow
docker load -i anomalytoolkit.tar

Write-Host "설정 완료! 다음 명령어로 서비스를 시작하세요:" -ForegroundColor Green
Write-Host "docker-compose up -d" -ForegroundColor Cyan
Write-Host "브라우저에서 http://localhost:8000/dashboard 로 접속하세요." -ForegroundColor Cyan
"@ | Out-File -FilePath "offline-package\setup.ps1" -Encoding utf8

# 7. 최종 tar.gz 파일 생성
Write-Host "최종 패키지 압축 중 (tar 방식)..." -ForegroundColor Yellow
if (Test-Path "anomaly-toolkit-offline-windows.tar.gz") {
    Remove-Item "anomaly-toolkit-offline-windows.tar.gz" -Force
}

tar -czf anomaly-toolkit-offline-windows.tar.gz -C offline-package .

# 8. 정리
Write-Host "임시 파일 정리 중..." -ForegroundColor Yellow
Remove-Item "anomalytoolkit.tar" -Force -ErrorAction SilentlyContinue
Remove-Item "offline-package" -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "빌드 완료!" -ForegroundColor Green
Write-Host "anomaly-toolkit-offline-windows.tar.gz 파일이 생성되었습니다." -ForegroundColor Green
Write-Host "이 파일을 Windows 환경에 복사하여 사용하세요." -ForegroundColor Green