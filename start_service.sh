#!/bin/bash
# Apple Silicon MacBook용 서비스 시작 스크립트 - start_service.sh

# 색상 설정
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${GREEN}LOGSCO 이상 로그 탐지 서비스 시작 중 (Apple Silicon)...${NC}"

# Docker가 실행 중인지 확인
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Docker가 실행되지 않았습니다. Docker Desktop을 시작해주세요.${NC}"
    exit 1
fi

# .env 파일 존재 확인
if [ ! -f ".env" ]; then
    echo -e "${RED}.env 파일이 없습니다. 먼저 ./setup.sh를 실행해주세요.${NC}"
    exit 1
fi

# SECRET_KEY 확인
if ! grep -q "SECRET_KEY=" .env || grep -q "SECRET_KEY=$" .env; then
    echo -e "${RED}.env 파일에 SECRET_KEY가 설정되지 않았습니다. ./setup.sh를 다시 실행해주세요.${NC}"
    exit 1
fi

# 기존 컨테이너 확인 및 정리
if [ "$(docker ps -q -f name=anomaly-detector)" ]; then
    echo -e "${YELLOW}기존 서비스 중지 중...${NC}"
    docker stop anomaly-detector
fi

if [ "$(docker ps -aq -f name=anomaly-detector)" ]; then
    echo -e "${YELLOW}기존 컨테이너 제거 중...${NC}"
    docker rm anomaly-detector
fi

# 필요한 디렉토리 생성
mkdir -p media logs db_data

# 서비스 시작 (Apple Silicon 최적화)
echo -e "${YELLOW}Apple Silicon용 컨테이너 시작 중... (ARM64 네이티브)${NC}"
docker run -d -p 8000:8000 --name anomaly-detector \
  --env-file .env \
  --platform linux/arm64 \
  -v "$PWD/media":/app/media \
  -v "$PWD/logs":/app/logs \
  -v "$PWD/db_data":/app/db_data \
  anomaly-toolkit:offline-arm64

# 서비스 상태 확인
echo -e "${CYAN}서비스 시작 확인 중...${NC}"
sleep 5

# 컨테이너가 실행 중인지 확인
if docker ps --format "table {{.Names}}\t{{.Status}}" | grep "anomaly-detector" | grep -q "Up"; then
    echo ""
    echo -e "${GREEN}🎉 서비스가 성공적으로 시작되었습니다!${NC}"
    echo -e "${GREEN}📁 파일 업로드: http://localhost:8000/upload/${NC}"
    echo -e "${GREEN}📊 분석 대시보드: http://localhost:8000/dashboard/${NC}"
    echo ""
    echo -e "${YELLOW}서비스 관리:${NC}"
    echo -e "${CYAN}  중지: ./stop_service.sh${NC}"
    echo -e "${CYAN}  로그 확인: docker logs anomaly-detector${NC}"
    echo -e "${CYAN}  상태 확인: docker ps${NC}"
else
    echo -e "${RED}❌ 서비스 시작에 실패했습니다. 로그를 확인하세요:${NC}"
    echo -e "${YELLOW}docker logs anomaly-detector${NC}"
fi