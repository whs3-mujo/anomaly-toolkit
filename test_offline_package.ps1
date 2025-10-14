# 오프라인 패키지 테스트 스크립트
# test_offline_package.ps1

Write-Host "LOGSCO 이상 로그 탐지 서비스 오프라인 패키지 테스트 시작..." -ForegroundColor Green

# 1. 테스트 폴더 생성
Write-Host "테스트 환경 준비 중..." -ForegroundColor Yellow
New-Item -Path "test-offline" -ItemType Directory -Force

# 2. 테스트 환경에 압축 해제
Write-Host "패키지 압축 해제 중..." -ForegroundColor Yellow
Expand-Archive -Path "anomaly-toolkit-offline.zip" -DestinationPath "test-offline" -Force

# 3. 테스트 환경으로 이동
Write-Host "테스트 환경으로 이동 중..." -ForegroundColor Yellow
Push-Location -Path "test-offline"

# 4. 설정 스크립트 실행
Write-Host "설정 스크립트 실행 중..." -ForegroundColor Yellow
.\setup.ps1

# 5. 서비스 시작
Write-Host "서비스 시작 중..." -ForegroundColor Yellow
docker-compose up -d

# 6. 서비스 상태 확인
Write-Host "서비스 상태 확인 중..." -ForegroundColor Yellow
docker-compose ps

Write-Host "테스트 환경이 준비되었습니다!" -ForegroundColor Green
Write-Host "브라우저에서 http://localhost:8000 으로 접속하여 테스트하세요." -ForegroundColor Cyan
Write-Host "테스트 완료 후 서비스 중지: docker-compose down" -ForegroundColor Yellow

# 원래 위치로 돌아오기
Pop-Location