@echo off
echo LOGSCO 이상 로그 탐지 서비스를 종료합니다...
echo.

REM 컨테이너 상태 확인
docker ps -a --filter "name=anomaly-detector" --format "table {{.Names}}\t{{.Status}}"

REM 컨테이너 중지
echo 컨테이너 중지 중...
docker stop anomaly-detector 2>nul

REM 컨테이너 제거  
echo 컨테이너 제거 중...
docker rm anomaly-detector 2>nul

echo.
echo 서비스가 종료되었습니다.
echo 데이터는 media 폴더에 보존됩니다.
pause