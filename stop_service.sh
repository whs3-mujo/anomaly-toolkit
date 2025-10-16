#!/bin/bash
# Apple Silicon MacBook용 서비스 중지 스크립트 - stop_service.sh

# 색상 설정
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${YELLOW}LOGSCO 이상 로그 탐지 서비스 중지 중...${NC}"

# 컨테이너 중지
if [ "$(docker ps -q -f name=anomaly-detector)" ]; then
    docker stop anomaly-detector
    echo -e "${GREEN}서비스가 중지되었습니다.${NC}"
else
    echo -e "${CYAN}실행 중인 서비스가 없습니다.${NC}"
fi

echo -e "${CYAN}✅ 다음 데이터가 보존됩니다:${NC}"
echo -e "${CYAN}  📁 media/ - 업로드된 파일들${NC}"
echo -e "${CYAN}  🗄️  db_data/ - 데이터베이스 (분석 결과, 세션 등)${NC}"
echo -e "${CYAN}  📋 logs/ - 서비스 로그${NC}"
echo ""
echo -e "${YELLOW}서비스 관리:${NC}"
echo -e "${CYAN}  재시작: ./start_service.sh${NC}"
echo -e "${CYAN}  완전 제거: docker stop anomaly-detector && docker rm anomaly-detector${NC}"
echo -e "${CYAN}  데이터 완전 삭제: rm -rf media db_data logs${NC}"