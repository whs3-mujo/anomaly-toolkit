# 오프라인 배포 패키지 빌드 스크립트
# build_offline_package.ps1

# 인코딩 설정
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "LOGSCO 이상 로그 탐지 서비스 오프라인 패키지 빌드 시작..." -ForegroundColor Green

# 1. 도커 이미지 빌드 (Windows용)
Write-Host "Windows용 오프라인 도커 이미지 빌드 중..." -ForegroundColor Yellow
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

# 5. Windows용 배치 스크립트 복사
Copy-Item -Path "start_service.bat" -Destination "offline-package\"
Copy-Item -Path "stop_service.bat" -Destination "offline-package\"
Copy-Item -Path "start_service_en.bat" -Destination "offline-package\"
Copy-Item -Path "stop_service_en.bat" -Destination "offline-package\"

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
Write-Host "start_service.bat를 더블클릭하거나 docker-compose up -d" -ForegroundColor Cyan
Write-Host "브라우저에서 http://localhost:8000/upload/ 또는 http://localhost:8000/dashboard/ 로 접속하세요." -ForegroundColor Cyan
"@ | Out-File -FilePath "offline-package\setup.ps1" -Encoding utf8


# 9. 안내 문서 생성 (Windows/macOS 통합)
@"
==== LOGSCO 이상 로그 탐지 서비스 오프라인 환경 실행 가이드 ====

1. 설치 전 준비사항
2. Windows 환경 실행 방법
3. 서비스 접속 및 사용법
4. 서비스 관리 
5. 트러블슈팅

═══════════════════════════════════════════════════════════════════

1. 설치 전 준비사항
   ✓ Docker Desktop 설치 필수
     - Windows: https://www.docker.com/products/docker-desktop
     - macOS: https://www.docker.com/products/docker-desktop
   ✓ 시스템 요구사항
     - Windows: Windows 10/11 또는 Windows Server 2019 이상
     - macOS: macOS 10.15 (Catalina) 이상
   ✓ 하드웨어: 최소 4GB RAM, 10GB 디스크 여유 공간

2. Windows 환경 실행 방법
   a. 압축 파일(.tar.gz)을 적당한 폴더에 압축 해제
      * Windows 10/11: 파일 우클릭 → "압축 풀기"
      * PowerShell: tar -xzf anomaly-toolkit-offline-windows.tar.gz
      * 7-Zip/WinRAR: 더블클릭으로 해제
   b. start_service.bat 파일을 더블클릭하여 실행
   c. 브라우저에서 http://localhost:8000/upload/ 또는 http://localhost:8000/dashboard/ 접속
   
   * 종료: stop_service.bat 파일 실행
   * 영어버전: start_service_en.bat, stop_service_en.bat 사용 가능

3. 서비스 접속 및 사용법
   ✓ 파일 업로드: http://localhost:8000/upload/
   ✓ 분석 대시보드: http://localhost:8000/dashboard/
   
   샘플 데이터: Final_Fintech_Security_Logs.csv 파일 활용

4. 서비스 관리 명령어
   Windows:
   - 시작: start_service.bat 더블클릭
   - 정지: stop_service.bat 더블클릭
   - 상태 확인: docker ps
   - 로그 확인: docker logs anomaly-detector
   - 재시작: docker restart anomaly-detector

5. 트러블슈팅
   문제상황 | 해결방법
   ──────────────────────────────────────────
   포트 8000 사용중 | 다른 프로그램 종료 후 재시작
   Docker 오류 | Docker Desktop 재시작
   접속 불가 | 방화벽 설정 확인
   + 리드미 파일 내 가이드북 참고
   
   
   ※ 데이터 초기화가 필요한 경우:
     docker stop anomaly-detector
     docker rm anomaly-detector  
     rmdir /s media
     mkdir media

═══════════════════════════════════════════════════════════════════

LOGSCO by TEAM 이상無조
기술지원: GitHub Issues (https://github.com/whs3-mujo/anomaly-toolkit)
라이선스: MIT License
지원 플랫폼: Windows 10/11

"@ | Out-File -FilePath "offline-package\README.txt" -Encoding utf8

# 8. 최종 tar.gz 파일 생성 (Windows용 - 대용량 파일 지원)
Write-Host "Windows용 패키지 압축 중 (tar 방식)..." -ForegroundColor Yellow
if (Test-Path "anomaly-toolkit-offline-windows.tar.gz") {
    Remove-Item "anomaly-toolkit-offline-windows.tar.gz" -Force
}

tar -czf anomaly-toolkit-offline-windows.tar.gz -C offline-package .

# 7. 정리
Write-Host "임시 파일 정리 중..." -ForegroundColor Yellow
Remove-Item "anomalytoolkit.tar" -Force -ErrorAction SilentlyContinue
Remove-Item "offline-package" -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "Windows용 빌드 완료!" -ForegroundColor Green
Write-Host "anomaly-toolkit-offline-windows.tar.gz 파일이 생성되었습니다." -ForegroundColor Green
Write-Host "이 파일을 Windows 환경에 복사하여 사용하세요." -ForegroundColor Green
