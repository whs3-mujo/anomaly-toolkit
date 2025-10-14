#!/bin/bash
# macOS용 서비스 중지 스크립트

# 색상 설정
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}LOGSCO 이상 로그 탐지 서비스 중지 중...${NC}"

# Docker가 실행 중인지 확인
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Docker가 실행되지 않았습니다.${NC}"
    exit 1
fi

# 컨테이너 중지
if [ "$(docker ps -q -f name=anomaly-detector)" ]; then
    echo "서비스 중지 중..."
    docker stop anomaly-detector
    echo -e "${GREEN}서비스가 중지되었습니다.${NC}"
else
    echo -e "${YELLOW}실행 중인 서비스가 없습니다.${NC}"
fi

# 컨테이너 제거
if [ "$(docker ps -aq -f name=anomaly-detector)" ]; then
    echo "컨테이너 제거 중..."
    docker rm anomaly-detector
    echo -e "${GREEN}컨테이너가 제거되었습니다.${NC}"
fi

echo -e "${GREEN}서비스 중지 완료!${NC}"