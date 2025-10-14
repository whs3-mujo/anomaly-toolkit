# 오프라인 배포 패키지 빌드 스크립트
# build_offline_package.ps1

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

# 4. 설치 스크립트 생성
@"
# PowerShell 스크립트 - setup.ps1
Write-Host "LOGSCO 이상 로그 탐지 서비스 설정 중..." -ForegroundColor Green

# 환경 변수 파일 생성
if (-not (Test-Path -Path ".env")) {
    Write-Host "환경 변수 파일 생성 중..." -ForegroundColor Yellow
    `$secretKey = -join ((65..90) + (97..122) | Get-Random -Count 50 | ForEach-Object {[char]`$_})
    "SECRET_KEY=`$secretKey" | Out-File -FilePath .env -Encoding utf8
}

# 도커 이미지 로드
Write-Host "도커 이미지 로딩 중... (잠시 시간이 소요될 수 있습니다)" -ForegroundColor Yellow
docker load -i anomalytoolkit.tar

Write-Host "설정 완료! 다음 명령어로 서비스를 시작하세요:" -ForegroundColor Green
Write-Host "docker-compose up -d" -ForegroundColor Cyan
Write-Host "브라우저에서 http://localhost:8000 으로 접속하세요." -ForegroundColor Cyan
"@ | Out-File -FilePath "offline-package\setup.ps1" -Encoding utf8

# 5. 안내 문서 생성
@"
==== LOGSCO 이상 로그 탐지 서비스 망분리 환경 실행 가이드 ====

1. 설치 전 준비사항
   - Docker Desktop이 설치되어 있어야 합니다.
   - PowerShell이 실행 가능해야 합니다.

2. 설치 및 실행 방법
   a. 이 폴더의 모든 파일을 대상 PC에 복사합니다.
   b. PowerShell을 관리자 권한으로 실행합니다.
   c. 이 폴더로 이동한 후 다음 명령어를 실행합니다:
      > .\setup.ps1
   d. 설정이 완료되면 다음 명령어로 서비스를 시작합니다:
      > docker-compose up -d

3. 서비스 접속 방법
   - 웹 브라우저에서 http://localhost:8000 으로 접속합니다.
   - 업로드: http://localhost:8000/upload/
   - 대시보드: http://localhost:8000/dashboard/

4. 서비스 관리 명령어
   - 서비스 상태 확인: docker-compose ps
   - 로그 확인: docker-compose logs -f
   - 서비스 중지: docker-compose down
   - 서비스 재시작: docker-compose restart

5. 트러블슈팅
   - 서비스 실행 문제 발생 시 로그 확인: docker-compose logs -f
   - 데이터 초기화: docker-compose down -v (주의: 모든 데이터가 삭제됩니다)
"@ | Out-File -FilePath "offline-package\README.txt" -Encoding utf8

# 6. 최종 zip 파일 생성
Write-Host "최종 패키지 압축 중..." -ForegroundColor Yellow
Compress-Archive -Path "offline-package\*" -DestinationPath "anomaly-toolkit-offline.zip" -Force

Write-Host "빌드 완료!" -ForegroundColor Green
Write-Host "anomaly-toolkit-offline.zip 파일이 생성되었습니다." -ForegroundColor Green
Write-Host "이 파일을 망분리 환경에 복사하여 사용하세요." -ForegroundColor Green