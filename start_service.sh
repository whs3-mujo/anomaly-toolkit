#!/bin/bash
# macOS용 서비스 시작 스크립트

# 색상 설정
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}LOGSCO 이상 로그 탐지 서비스 시작 중...${NC}"

# Docker가 실행 중인지 확인
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Docker가 실행되지 않았습니다. Docker Desktop을 시작해주세요.${NC}"
    exit 1
fi

# 기존 컨테이너가 있다면 중지 및 제거
if [ "$(docker ps -q -f name=anomaly-detector)" ]; then
    echo "기존 서비스 중지 중..."
    docker stop anomaly-detector
fi

if [ "$(docker ps -aq -f name=anomaly-detector)" ]; then
    echo "기존 컨테이너 제거 중..."
    docker rm anomaly-detector
fi

# SECRET_KEY 자동 생성 (환경 파일이 없는 경우)
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}환경 변수 파일 생성 중...${NC}"
    cp .env.example .env
    SECRET_KEY=$(openssl rand -base64 50 | tr -d "=+/" | cut -c1-50)
    sed -i '' "s/SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" .env
    echo -e "${GREEN}새로운 SECRET_KEY가 생성되었습니다.${NC}"
fi

# 서비스 시작
echo -e "${YELLOW}Docker 이미지 로딩 중...${NC}"
docker load -i anomalytoolkit.tar > /dev/null 2>&1

echo -e "${YELLOW}서비스 시작 중...${NC}"
docker run -d -p 8000:8000 --name anomaly-detector anomaly-toolkit:offline

echo ""
echo -e "${GREEN}서비스가 성공적으로 시작되었습니다!${NC}"
echo -e "${GREEN}파일 업로드: http://localhost:8000/upload/${NC}"
echo -e "${GREEN}분석 대시보드: http://localhost:8000/dashboard/${NC}"
echo ""
echo -e "${YELLOW}서비스를 중지하려면 './stop_service.sh'를 실행하세요.${NC}"