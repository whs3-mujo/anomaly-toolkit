@echo off
echo LOGSCO 이상 로그 탐지 서비스를 시작합니다...
echo.

REM 도커 이미지 로드
echo 도커 이미지 로딩 중...
docker load -i anomalytoolkit.tar

REM 서비스 시작
echo 서비스 시작 중...
docker run -d -p 8000:8000 --name anomaly-detector anomaly-toolkit:offline

echo.
echo 서비스가 시작되었습니다!
echo 웹 브라우저에서 http://localhost:8000 으로 접속하세요.
echo 업로드: http://localhost:8000/upload/
echo 대시보드: http://localhost:8000/dashboard/
echo.
echo 서비스를 종료하려면 'stop_service.bat' 파일을 실행하세요.
pause