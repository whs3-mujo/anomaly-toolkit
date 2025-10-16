#!/bin/bash
# M1 Pro/M2 MacBook용 초기 설정 스크립트 - setup.sh

# 색상 설정
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}LOGSCO 이상 로그 탐지 서비스 설정 중 (Apple Silicon 최적화)...${NC}"

# Docker 확인
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Docker가 실행되지 않았습니다. Docker Desktop을 시작해주세요.${NC}"
    exit 1
fi

# 환경 변수 파일 생성
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}환경 변수 파일 생성 중...${NC}"
    cp .env.example .env
    
    # SECRET_KEY 자동 생성
    echo -e "${YELLOW}Django SECRET_KEY 생성 중...${NC}"
    SECRET_KEY=$(openssl rand -base64 50 | tr -d "=+/\n" | cut -c1-50)
    
    # SECRET_KEY가 제대로 생성되었는지 확인
    if [ -z "$SECRET_KEY" ]; then
        echo -e "${RED}SECRET_KEY 생성 실패. 기본값을 사용합니다.${NC}"
        SECRET_KEY="django-insecure-m1pro-key-$(date +%s)"
    fi
    
    # .env 파일에 SECRET_KEY 설정 (macOS sed 호환)
    sed -i '' "s|SECRET_KEY=.*|SECRET_KEY=${SECRET_KEY}|" .env
    
    echo -e "${GREEN}새로운 SECRET_KEY가 생성되었습니다: ${SECRET_KEY:0:20}...${NC}"
else
    echo -e "${CYAN}.env 파일이 이미 존재합니다.${NC}"
    # 기존 .env에 SECRET_KEY가 비어있는지 확인
    if grep -q "SECRET_KEY=$" .env || grep -q "SECRET_KEY=\"\"" .env; then
        echo -e "${YELLOW}비어있는 SECRET_KEY를 새로 생성합니다...${NC}"
        SECRET_KEY=$(openssl rand -base64 50 | tr -d "=+/\n" | cut -c1-50)
        sed -i '' "s|SECRET_KEY=.*|SECRET_KEY=${SECRET_KEY}|" .env
        echo -e "${GREEN}SECRET_KEY가 업데이트되었습니다.${NC}"
    fi
fi

# 필요한 디렉토리 생성
mkdir -p media logs db_data
echo -e "${CYAN}필요한 디렉토리가 생성되었습니다.${NC}"

# 스크립트 실행 권한 부여
chmod +x start_service.sh
chmod +x stop_service.sh

# 도커 이미지 로드
echo -e "${YELLOW}Apple Silicon용 도커 이미지 로딩 중... (ARM64 네이티브)${NC}"
docker load -i anomaly-toolkit-arm64.tar

echo -e "${GREEN}설정 완료! 다음 명령어로 서비스를 시작하세요:${NC}"
echo -e "${CYAN}./start_service.sh${NC}"
echo ""
echo -e "${GREEN}브라우저에서 다음 주소로 접속하세요:${NC}"
echo -e "${CYAN}📁 파일 업로드: http://localhost:8000/upload/${NC}"
echo -e "${CYAN}📊 분석 대시보드: http://localhost:8000/dashboard/${NC}"
echo ""
echo -e "${YELLOW}문제 발생 시 진단 명령어:${NC}"
echo -e "${CYAN}docker logs anomaly-detector${NC} - 서비스 로그 확인"
echo -e "${CYAN}docker ps${NC} - 컨테이너 상태 확인"
echo -e "${CYAN}cat .env | grep SECRET_KEY${NC} - SECRET_KEY 확인"