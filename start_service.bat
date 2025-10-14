@echo off
title LOGSCO Service
powershell.exe -ExecutionPolicy Bypass -Command "& {[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; .\service.ps1 start}"
echo.

REM 도커 이미지 로드
echo 도커 이미지 로딩 중...
docker load -i anomalytoolkit.tar

REM .env 파일 확인 및 생성
if not exist .env (
    echo 환경 설정 파일 생성 중...
    copy .env.example .env
    echo SECRET_KEY를 변경하세요!
)

REM 서비스 시작 (볼륨 마운트 포함)
echo 서비스 시작 중...
docker run -d ^
    -p 8000:8000 ^
    --name anomaly-detector ^
    -v "%cd%\media:/app/media" ^
    -v "%cd%\logs:/app/logs" ^
    --env-file .env ^
    anomaly-toolkit:offline

echo.
echo 서비스가 시작되었습니다!
echo 웹 브라우저에서 http://localhost:8000/dashboard 로 접속하세요.
echo 업로드: http://localhost:8000/upload/
echo 대시보드: http://localhost:8000/dashboard/
echo.
echo 서비스를 종료하려면 'stop_service.bat' 파일을 실행하세요.
pause