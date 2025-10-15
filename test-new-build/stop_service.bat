@echo off
@echo off
title LOGSCO Service Stop
powershell.exe -ExecutionPolicy Bypass -Command "& {[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; .\service.ps1 stop}"
echo.

REM 컨테이너 상태 확인
docker-compose ps

REM 서비스 중지
echo 서비스 중지 중...
docker-compose stop

echo.
echo 서비스가 종료되었습니다.
echo 데이터는 media 폴더에 보존됩니다.
pause