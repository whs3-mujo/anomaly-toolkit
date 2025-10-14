@echo off
chcp 65001 > nul
echo Stopping LOGSCO Anomaly Detection Service...
docker stop anomaly-detector
docker rm anomaly-detector
echo Service stopped successfully.
pause