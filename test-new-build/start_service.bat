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
    copy .env.example .env >nul
    echo SECRET_KEY 자동 생성 중...
    powershell -Command "$key = 'django-insecure-' + (Get-Date -Format 'yyyyMMddHHmmss') + '-auto-generated'; (Get-Content '.env') -replace 'SECRET_KEY=.*', \"SECRET_KEY=$key\" | Set-Content '.env'" 2>nul
    echo 환경 설정 완료!
)

REM 기존 서비스 정리
docker-compose stop 2>nul

REM 서비스 시작 (Docker Compose 사용)
echo 서비스 시작 중...
docker-compose up -d

echo.
echo 서비스가 시작되었습니다!
echo 웹 브라우저에서 http://localhost:8000/dashboard 로 접속하세요.
echo 업로드: http://localhost:8000/upload/
echo 대시보드: http://localhost:8000/dashboard/
echo.
echo 서비스를 종료하려면 'stop_service.bat' 파일을 실행하세요.
pause