#!/bin/bash
# 오프라인 패키지 테스트 스크립트 (macOS/Linux 용)
# test_offline_package.sh

echo "LOGSCO 이상 로그 탐지 서비스 오프라인 패키지 테스트 시작..."

# 1. 테스트 폴더 생성
echo "테스트 환경 준비 중..."
mkdir -p test-offline-mac

# 2. 테스트 환경에 압축 해제
echo "패키지 압축 해제 중..."
unzip -o anomaly-toolkit-offline-mac.zip -d test-offline-mac

# 3. 테스트 환경으로 이동
echo "테스트 환경으로 이동 중..."
cd test-offline-mac

# 4. 설치 스크립트에 실행 권한 부여
echo "실행 권한 부여 중..."
chmod +x setup.sh

# 5. 설정 스크립트 실행
echo "설정 스크립트 실행 중..."
./setup.sh

# 6. 서비스 시작
echo "서비스 시작 중..."
docker-compose up -d

# 7. 서비스 상태 확인
echo "서비스 상태 확인 중..."
docker-compose ps

echo "테스트 환경이 준비되었습니다!"
echo "브라우저에서 http://localhost:8000 으로 접속하여 테스트하세요."
echo "테스트 완료 후 서비스 중지: docker-compose down"

# 원래 위치로 돌아오기
cd ..