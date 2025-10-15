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

# Docker Compose 파일 복사 및 수정
$dockerComposeContent = Get-Content "docker-compose.offline.yml" -Raw
$dockerComposeContent = $dockerComposeContent -replace "container_name: anomalytoolkit-web", "container_name: anomaly-detector"
$dockerComposeContent | Out-File -FilePath "offline-package\docker-compose.yml" -Encoding utf8

Copy-Item -Path "anomalytoolkit.tar" -Destination "offline-package\"

# 빈 디렉터리만 생성 (테스트 데이터 포함하지 않음)
New-Item -Path "offline-package\media" -ItemType Directory -Force
New-Item -Path "offline-package\logs" -ItemType Directory -Force

Write-Host "패키지에서 테스트 데이터 제외됨 (깨끗한 설치)" -ForegroundColor Cyan

# 4. 환경 설정 파일 복사
Copy-Item -Path ".env.example" -Destination "offline-package\"

# 5. macOS용 쉘 스크립트 생성
$startScript = @"
#!/bin/bash
# macOS용 서비스 시작 스크립트 (Docker Compose 사용)

# 색상 설정
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "`${GREEN}LOGSCO 이상 로그 탐지 서비스 시작 중...`${NC}"

# Docker가 실행 중인지 확인
if ! docker info > /dev/null 2>&1; then
    echo -e "`${RED}Docker가 실행되지 않았습니다. Docker Desktop을 시작해주세요.`${NC}"
    exit 1
fi

# .env 파일 존재 확인
if [ ! -f ".env" ]; then
    echo -e "`${RED}.env 파일이 없습니다. 먼저 ./setup.sh를 실행해주세요.`${NC}"
    exit 1
fi

# SECRET_KEY 확인
if ! grep -q "SECRET_KEY=" .env || grep -q "SECRET_KEY=$" .env; then
    echo -e "`${RED}.env 파일에 SECRET_KEY가 설정되지 않았습니다. ./setup.sh를 다시 실행해주세요.`${NC}"
    exit 1
fi

# 기존 서비스 확인 및 재시작
echo -e "`${YELLOW}기존 서비스 확인 중...`${NC}"
if docker-compose ps | grep -q "anomaly-detector"; then
    echo -e "`${CYAN}기존 컨테이너 발견. 재시작합니다...`${NC}"
    docker-compose restart
else
    echo -e "`${YELLOW}새 컨테이너를 시작합니다...`${NC}"
    docker-compose up -d
fi

# 서비스 상태 확인
sleep 3
if docker-compose ps | grep -q "Up"; then
    echo ""
    echo -e "`${GREEN}서비스가 성공적으로 시작되었습니다!`${NC}"
    echo -e "`${GREEN}파일 업로드: http://localhost:8000/upload/`${NC}"
    echo -e "`${GREEN}분석 대시보드: http://localhost:8000/dashboard/`${NC}"
    echo ""
    echo -e "`${YELLOW}서비스를 중지하려면 './stop_service.sh'를 실행하세요.`${NC}"
    echo -e "`${YELLOW}로그 확인: docker-compose logs -f`${NC}"
else
    echo -e "`${RED}서비스 시작에 실패했습니다. 로그를 확인하세요:`${NC}"
    echo -e "`${YELLOW}docker-compose logs`${NC}"
fi
"@

$stopScript = @"
#!/bin/bash
# macOS용 서비스 중지 스크립트 (데이터 보존)

# 색상 설정
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "`${YELLOW}LOGSCO 이상 로그 탐지 서비스 중지 중...`${NC}"

# 컨테이너만 중지
docker-compose stop

echo -e "`${GREEN}서비스가 중지되었습니다.`${NC}"
echo -e "`${CYAN}데이터베이스와 업로드 파일이 보존됩니다.`${NC}"
echo -e "`${CYAN}완전히 제거하려면: docker-compose down`${NC}"
"@

$startScript -replace "`r`n", "`n" | Out-File -FilePath "offline-package\start_service.sh" -Encoding utf8 -NoNewline
$stopScript -replace "`r`n", "`n" | Out-File -FilePath "offline-package\stop_service.sh" -Encoding utf8 -NoNewline

# 6. macOS용 설치 스크립트 생성
$setupScript = @"
#!/bin/bash
# macOS용 설치 스크립트 - setup.sh

# 색상 설정
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "`${GREEN}LOGSCO 이상 로그 탐지 서비스 설정 중...`${NC}"

# 환경 변수 파일 생성
if [ ! -f ".env" ]; then
    echo -e "`${YELLOW}환경 변수 파일 생성 중...`${NC}"
    cp .env.example .env
    
    # SECRET_KEY 자동 생성
    echo -e "`${YELLOW}Django SECRET_KEY 생성 중...`${NC}"
    SECRET_KEY=`$(python3 -c "
import secrets
import string
alphabet = string.ascii_letters + string.digits + '!@#$%^&*(-_=+)'
print(''.join(secrets.choice(alphabet) for i in range(50)))
")
    
    # SECRET_KEY가 제대로 생성되었는지 확인
    if [ -z "`$SECRET_KEY" ]; then
        echo -e "`${RED}Python3가 없어서 openssl로 SECRET_KEY 생성을 시도합니다...`${NC}"
        SECRET_KEY=`$(openssl rand -base64 50 | tr -d "=+/" | cut -c1-50)
    fi
    
    # SECRET_KEY가 여전히 비어있다면 기본값 사용
    if [ -z "`$SECRET_KEY" ]; then
        echo -e "`${RED}SECRET_KEY 자동 생성 실패. 기본값을 사용합니다.`${NC}"
        SECRET_KEY="django-insecure-default-key-please-change-in-production-`$(date +%s)"
    fi
    
    # .env 파일에 SECRET_KEY 설정 (macOS sed 호환)
    if [[ "`$OSTYPE" == "darwin"* ]]; then
        # macOS용 sed (BSD sed)
        sed -i '' "s|SECRET_KEY=.*|SECRET_KEY=`$SECRET_KEY|" .env
    else
        # Linux용 sed (GNU sed)
        sed -i "s|SECRET_KEY=.*|SECRET_KEY=`$SECRET_KEY|" .env
    fi
    
    echo -e "`${GREEN}새로운 SECRET_KEY가 생성되었습니다: `${SECRET_KEY:0:20}...`${NC}"
else
    echo -e "`${CYAN}.env 파일이 이미 존재합니다.`${NC}"
    # 기존 .env에 SECRET_KEY가 비어있는지 확인
    if grep -q "SECRET_KEY=$" .env || grep -q "SECRET_KEY=\"\"" .env; then
        echo -e "`${YELLOW}비어있는 SECRET_KEY를 새로 생성합니다...`${NC}"
        SECRET_KEY=`$(python3 -c "
import secrets
import string
alphabet = string.ascii_letters + string.digits + '!@#$%^&*(-_=+)'
print(''.join(secrets.choice(alphabet) for i in range(50)))
" 2>/dev/null || openssl rand -base64 50 | tr -d "=+/" | cut -c1-50)
        
        if [[ "`$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|SECRET_KEY=.*|SECRET_KEY=`$SECRET_KEY|" .env
        else
            sed -i "s|SECRET_KEY=.*|SECRET_KEY=`$SECRET_KEY|" .env
        fi
        echo -e "`${GREEN}SECRET_KEY가 업데이트되었습니다.`${NC}"
    fi
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
echo ""
echo -e "`${YELLOW}문제 발생 시 진단 명령어:`${NC}"
echo -e "`${CYAN}docker-compose logs`${NC} - 서비스 로그 확인"
echo -e "`${CYAN}docker-compose ps`${NC} - 컨테이너 상태 확인"
echo -e "`${CYAN}cat .env | grep SECRET_KEY`${NC} - SECRET_KEY 확인"
"@

# Unix 줄바꿈으로 변환하여 저장
$setupScript -replace "`r`n", "`n" | Out-File -FilePath "offline-package\setup.sh" -Encoding utf8 -NoNewline


# 7. macOS용 README 생성
@"
==== LOGSCO 이상 로그 탐지 서비스 macOS용 오프라인 환경 실행 가이드 ====

1. 설치 전 준비사항
2. macOS 환경 실행 방법
3. 서비스 접속 및 사용법
4. 서비스 관리 
5. 트러블슈팅

═══════════════════════════════════════════════════════════════════

1. 설치 전 준비사항
   ✓ Docker Desktop for Mac 설치 필수
     - 다운로드: https://www.docker.com/products/docker-desktop
   ✓ 시스템 요구사항
     - macOS 10.15 (Catalina) 이상
     - Intel Mac 및 Apple Silicon Mac 모두 지원 (Rosetta 2 호환)
   ✓ 하드웨어: 최소 4GB RAM, 10GB 디스크 여유 공간

2. macOS 환경 실행 방법
   a. 압축 파일(.tar.gz)을 적당한 폴더에 압축 해제
      * 터미널: tar -xzf anomaly-toolkit-offline-macos-amd64.tar.gz
      * Finder: 더블클릭으로 해제
   b. 터미널을 열고 해당 폴더로 이동
   c. chmod +x *.sh 실행 (권한 설정)
   d. ./setup.sh 실행 (최초 1회)
   e. ./start_service.sh 실행
   f. 브라우저에서 http://localhost:8000/upload/ 또는 http://localhost:8000/dashboard/ 접속
   
   * 종료: ./stop_service.sh 실행

3. 서비스 접속 및 사용법
   ✓ 파일 업로드: http://localhost:8000/upload/
   ✓ 분석 대시보드: http://localhost:8000/dashboard/
   
   샘플 데이터: Final_Fintech_Security_Logs.csv 파일 활용

4. 서비스 관리 명령어
   - 시작: ./start_service.sh (기존 데이터 보존)
   - 정지: ./stop_service.sh (데이터 보존, 컨테이너 유지)
   - 상태 확인: docker-compose ps
   - 로그 확인: docker-compose logs
   - 재시작: docker-compose restart
   - 완전 제거: docker-compose down (주의: 데이터 삭제됨)

5. 트러블슈팅
   문제상황 | 해결방법
   ──────────────────────────────────────────
   포트 8000 사용중 | sudo lsof -i :8000 으로 확인 후 종료
   Docker 오류 | Docker Desktop 재시작
   권한 오류 | chmod +x *.sh 실행
   접속 불가 | 방화벽 설정 확인
   Apple Silicon 호환성 | Rosetta 2 자동으로 처리됨
   SECRET_KEY 오류 | ./setup.sh 재실행 또는 .env 파일 확인
   데이터 손실 방지 | stop_service.sh 사용 (down 명령어 지양)
   
   ※ 데이터 보존하며 재시작:
     ./stop_service.sh && ./start_service.sh
   
   ※ 완전 초기화가 필요한 경우만:
     docker-compose down
     rm -rf media logs
     mkdir media logs

═══════════════════════════════════════════════════════════════════

LOGSCO by TEAM 이상無조
기술지원: GitHub Issues (https://github.com/whs3-mujo/anomaly-toolkit)
라이선스: MIT License

"@ | Out-File -FilePath "offline-package\README.txt" -Encoding utf8

# 8. 최종 tar.gz 파일 생성
Write-Host "macOS용 패키지 압축 중 (tar 방식)..." -ForegroundColor Yellow
if (Test-Path "anomaly-toolkit-offline-macos-amd64.tar.gz") {
    Remove-Item "anomaly-toolkit-offline-macos-amd64.tar.gz" -Force
}

# tar 명령어 사용
tar -czf anomaly-toolkit-offline-macos-amd64.tar.gz -C offline-package .

# 9. 정리
Write-Host "임시 파일 정리 중..." -ForegroundColor Yellow
Remove-Item "anomalytoolkit.tar" -Force -ErrorAction SilentlyContinue
Remove-Item "offline-package" -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "macOS용 빌드 완료! (AMD64 호환)" -ForegroundColor Green
Write-Host "anomaly-toolkit-offline-macos-amd64.tar.gz 파일이 생성되었습니다." -ForegroundColor Green
Write-Host "Intel Mac: 네이티브 실행 / Apple Silicon Mac: Rosetta 2 호환 실행" -ForegroundColor Cyan
Write-Host "이 파일을 macOS 환경에 복사하여 사용하세요." -ForegroundColor Green