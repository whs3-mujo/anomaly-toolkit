@echo off
echo LOGSCO 이상 로그 탐지 서비스를 종료합니다...
docker stop anomaly-detector
docker rm anomaly-detector
echo 서비스가 종료되었습니다.
pause