# macOS용 오프라인 배포 패키지 빌드 스크립트 (AMD64 only - 빠른 빌드)
# macos_amd64_build_package.ps1

# 인코딩 설정
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "LOGSCO 이상 로그 탐지 서비스 macOS용 오프라인 패키지 빌드 시작 (AMD64 전용)..." -ForegroundColor Green

# 1. macOS용 도커 이미지 빌드 (AMD64만 - 빠른 빌드)
Write-Host "macOS용 오프라인 도커 이미지 빌드 중 (AMD64 전용, Intel + Apple Silicon 호환)..." -ForegroundColor Yellow
docker build -f Dockerfile.offline --platform linux/amd64 -t anomaly-toolkit:offline .

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

# 5. macOS용 쉘 스크립트 복사
Copy-Item -Path "start_service.sh" -Destination "offline-package\"
Copy-Item -Path "stop_service.sh" -Destination "offline-package\"

# 6. macOS용 설치 스크립트 생성
@"
#!/bin/bash
# macOS용 설치 스크립트 - setup.sh

# 색상 설정
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "`${GREEN}LOGSCO 이상 로그 탐지 서비스 설정 중...`${NC}"

# 환경 변수 파일 생성
if [ ! -f ".env" ]; then
    echo -e "`${YELLOW}환경 변수 파일 생성 중...`${NC}"
    cp .env.example .env
    
    # SECRET_KEY 자동 생성 (macOS용)
    SECRET_KEY=`$(openssl rand -base64 50 | tr -d "=+/" | cut -c1-50)
    sed -i '' "s/SECRET_KEY=.*/SECRET_KEY=`$SECRET_KEY/" .env
    echo -e "`${GREEN}새로운 SECRET_KEY가 생성되었습니다.`${NC}"
fi

# 스크립트 실행 권한 부여
chmod +x start_service.sh
chmod +x stop_service.sh

# 도커 이미지 로드
echo -e "`${YELLOW}도커 이미지 로딩 중... (잠시 시간이 소요될 수 있습니다)`${NC}"
docker load -i anomalytoolkit.tar

echo -e "`${GREEN}설정 완료! 다음 명령어로 서비스를 시작하세요:`${NC}"
echo -e "`${CYAN}./start_service.sh`${NC}"
echo -e "`${CYAN}브라우저에서 http://localhost:8000/upload/ 또는 http://localhost:8000/dashboard/ 로 접속하세요.`${NC}"
"@ | Out-File -FilePath "offline-package\setup.sh" -Encoding utf8


# 8. 최종 zip 파일 생성 (macOS용 - AMD64)
Write-Host "macOS용 패키지 압축 중 (AMD64 호환)..." -ForegroundColor Yellow
if (Test-Path "anomaly-toolkit-offline-macos-amd64.zip") {
    Remove-Item "anomaly-toolkit-offline-macos-amd64.zip" -Force
}
Compress-Archive -Path "offline-package\*" -DestinationPath "anomaly-toolkit-offline-macos-amd64.zip" -Force

# 9. 정리
Write-Host "임시 파일 정리 중..." -ForegroundColor Yellow
Remove-Item "anomalytoolkit.tar" -Force -ErrorAction SilentlyContinue
Remove-Item "offline-package" -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "macOS용 빌드 완료! (AMD64 호환)" -ForegroundColor Green
Write-Host "anomaly-toolkit-offline-macos-amd64.zip 파일이 생성되었습니다." -ForegroundColor Green
Write-Host "Intel Mac: 네이티브 실행 / Apple Silicon Mac: Rosetta 2 호환 실행" -ForegroundColor Cyan
Write-Host "이 파일을 macOS 환경에 복사하여 사용하세요." -ForegroundColor Green