@echo off
chcp 65001 > nul
echo Starting LOGSCO Anomaly Detection Service...
echo.

REM Loading Docker image
echo Loading Docker image...
docker load -i anomalytoolkit.tar

REM Starting service
echo Starting service...
docker run -d -p 8000:8000 --name anomaly-detector anomaly-toolkit:offline

echo.
echo Service started successfully!
echo Access the service at http://localhost:8000
echo Upload logs: http://localhost:8000/upload/
echo View dashboard: http://localhost:8000/dashboard/
echo.
echo To stop the service, run 'stop_service.bat'
pause