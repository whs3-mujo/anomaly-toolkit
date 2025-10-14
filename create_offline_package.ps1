# 오프라인 환경 배포를 위한 최종 패키지 생성 스크립트
# 개발자용 - 오프라인 배포 패키지를 생성하는 스크립트입니다.
# 최종 사용자는 이 스크립트를 실행할 필요가 없습니다.
# 참고: 한글 인코딩 문제를 해결하기 위해 영어 버전의 배치 파일도 함께 생성합니다.

Write-Host "LOGSCO 이상 로그 탐지 서비스 배포 패키지 생성 중..." -ForegroundColor Green

# 1. 도커 이미지 빌드
Write-Host "도커 이미지 빌드 중..." -ForegroundColor Yellow
docker build -t anomaly-toolkit:offline .

# 2. 도커 이미지를 tar 파일로 저장
Write-Host "도커 이미지 저장 중..." -ForegroundColor Yellow
docker save -o anomalytoolkit.tar anomaly-toolkit:offline

# 3. 배포 패키지 디렉터리 생성
Write-Host "배포 패키지 준비 중..." -ForegroundColor Yellow
New-Item -Path "dist" -ItemType Directory -Force
Copy-Item -Path "anomalytoolkit.tar" -Destination "dist\"

# 4. 간단한 시작 스크립트 생성 (Windows 용)
$startContent = "@echo off`r`n" +
"echo LOGSCO 이상 로그 탐지 서비스를 시작합니다...`r`n" +
"echo.`r`n`r`n" +
"REM 도커 이미지 로드`r`n" +
"echo 도커 이미지 로딩 중...`r`n" +
"docker load -i anomalytoolkit.tar`r`n`r`n" +
"REM 서비스 시작`r`n" +
"echo 서비스 시작 중...`r`n" +
"docker run -d -p 8000:8000 --name anomaly-detector anomaly-toolkit:offline`r`n`r`n" +
"echo.`r`n" +
"echo 서비스가 시작되었습니다!`r`n" +
"echo 웹 브라우저에서 http://localhost:8000 으로 접속하세요.`r`n" +
"echo 업로드: http://localhost:8000/upload/`r`n" +
"echo 대시보드: http://localhost:8000/dashboard/`r`n" +
"echo.`r`n" +
"echo 서비스를 종료하려면 'stop_service.bat' 파일을 실행하세요.`r`n" +
"pause"

# 유니코드 없이 직접 파일에 쓰기
[System.IO.File]::WriteAllText("dist\start_service.bat", $startContent, [System.Text.Encoding]::ASCII)

# 5. 서비스 종료 스크립트 (Windows 용)
$stopContent = "@echo off`r`n" +
"echo LOGSCO 이상 로그 탐지 서비스를 종료합니다...`r`n" +
"docker stop anomaly-detector`r`n" +
"docker rm anomaly-detector`r`n" +
"echo 서비스가 종료되었습니다.`r`n" +
"pause"

# 유니코드 없이 직접 파일에 쓰기
[System.IO.File]::WriteAllText("dist\stop_service.bat", $stopContent, [System.Text.Encoding]::ASCII)

# 6. 간단한 시작 스크립트 생성 (macOS/Linux 용)
@"
#!/bin/bash
echo "LOGSCO 이상 로그 탐지 서비스를 시작합니다..."
echo

# 도커 이미지 로드
echo "도커 이미지 로딩 중..."
docker load -i anomalytoolkit.tar

# 서비스 시작
echo "서비스 시작 중..."
docker run -d -p 8000:8000 --name anomaly-detector anomaly-toolkit:offline

echo
echo "서비스가 시작되었습니다!"
echo "웹 브라우저에서 http://localhost:8000 으로 접속하세요."
echo "업로드: http://localhost:8000/upload/"
echo "대시보드: http://localhost:8000/dashboard/"
echo
echo "서비스를 종료하려면 './stop_service.sh' 파일을 실행하세요."
"@ | Out-File -FilePath "dist\start_service.sh" -Encoding ASCII

# 7. 서비스 종료 스크립트 (macOS/Linux 용)
@"
#!/bin/bash
echo "LOGSCO 이상 로그 탐지 서비스를 종료합니다..."
docker stop anomaly-detector
docker rm anomaly-detector
echo "서비스가 종료되었습니다."
"@ | Out-File -FilePath "dist\stop_service.sh" -Encoding ASCII

# 8. README 파일 생성
@"
# LOGSCO 이상 로그 탐지 서비스 - 오프라인 실행 가이드

## 시작하기 전에
- Docker Desktop이 설치되어 있어야 합니다.
  - Windows: https://docs.docker.com/desktop/install/windows-install/
  - Mac: https://docs.docker.com/desktop/install/mac-install/
  - Linux: https://docs.docker.com/desktop/install/linux-install/

## 서비스 시작하기
### Windows 사용자
1. 'start_service.bat' 파일을 더블클릭하여 실행합니다.
2. 웹 브라우저에서 http://localhost:8000 으로 접속합니다.

### macOS/Linux 사용자
1. 터미널을 열고 이 폴더로 이동합니다.
2. 다음 명령어로 스크립트에 실행 권한을 부여합니다:
   ```
   chmod +x start_service.sh stop_service.sh
   ```
3. 다음 명령어로 서비스를 시작합니다:
   ```
   ./start_service.sh
   ```
4. 웹 브라우저에서 http://localhost:8000 으로 접속합니다.

## 서비스 사용하기
- 로그 파일 업로드: http://localhost:8000/upload/
- 분석 결과 확인: http://localhost:8000/dashboard/

## 서비스 종료하기
### Windows 사용자
- 'stop_service.bat' 파일을 더블클릭하여 실행합니다.

### macOS/Linux 사용자
- 터미널에서 다음 명령어를 실행합니다:
  ```
  ./stop_service.sh
  ```

## 트러블슈팅
서비스가 정상적으로 시작되지 않는 경우, 다음 명령어로 상태를 확인해 볼 수 있습니다:
```
docker ps -a
```

오류 로그를 확인하려면 다음 명령어를 실행합니다:
```
docker logs anomaly-detector
```
"@ | Out-File -FilePath "dist\README.md" -Encoding utf8

# 8.5 영어 버전 스크립트도 추가 (한글 인코딩 문제 해결)
$startContent_en = "@echo off`r`n" +
"chcp 65001 > nul`r`n" +
"echo Starting LOGSCO Anomaly Detection Service...`r`n" +
"echo.`r`n`r`n" +
"REM Loading Docker image`r`n" +
"echo Loading Docker image...`r`n" +
"docker load -i anomalytoolkit.tar`r`n`r`n" +
"REM Starting service`r`n" +
"echo Starting service...`r`n" +
"docker run -d -p 8000:8000 --name anomaly-detector anomaly-toolkit:offline`r`n`r`n" +
"echo.`r`n" +
"echo Service started successfully!`r`n" +
"echo Access the service at http://localhost:8000`r`n" +
"echo Upload logs: http://localhost:8000/upload/`r`n" +
"echo View dashboard: http://localhost:8000/dashboard/`r`n" +
"echo.`r`n" +
"echo To stop the service, run 'stop_service.bat'`r`n" +
"pause"

[System.IO.File]::WriteAllText("dist\start_service_en.bat", $startContent_en, [System.Text.Encoding]::ASCII)

$stopContent_en = "@echo off`r`n" +
"chcp 65001 > nul`r`n" +
"echo Stopping LOGSCO Anomaly Detection Service...`r`n" +
"docker stop anomaly-detector`r`n" +
"docker rm anomaly-detector`r`n" +
"echo Service stopped successfully.`r`n" +
"pause"

[System.IO.File]::WriteAllText("dist\stop_service_en.bat", $stopContent_en, [System.Text.Encoding]::ASCII)

# README에 영어 스크립트에 대한 내용 추가
$readmeContent = [System.IO.File]::ReadAllText("dist\README.md", [System.Text.Encoding]::UTF8)
$readmeContent = $readmeContent.Replace("## 서비스 시작하기", "## 서비스 시작하기`n`n**참고**: 한글 표시에 문제가 있는 경우 영어 버전 스크립트 (`start_service_en.bat`, `stop_service_en.bat`)를 사용하세요.")
[System.IO.File]::WriteAllText("dist\README.md", $readmeContent, [System.Text.Encoding]::UTF8)

# 9. 최종 패키지 압축
Write-Host "최종 패키지 압축 중..." -ForegroundColor Yellow
Compress-Archive -Path "dist\*" -DestinationPath "logsco-anomaly-detector.zip" -Force

Write-Host "배포 패키지 생성 완료!" -ForegroundColor Green
Write-Host "logsco-anomaly-detector.zip 파일이 생성되었습니다." -ForegroundColor Green
Write-Host "이 파일을 사용자들에게 배포하면 됩니다." -ForegroundColor Green