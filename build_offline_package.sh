#!/bin/bash
# 오프라인 배포 패키지 빌드 스크립트 (macOS/Linux 용)
# build_offline_package.sh

echo "LOGSCO 이상 로그 탐지 서비스 오프라인 패키지 빌드 시작..."

# 1. 도커 이미지 빌드
echo "오프라인 환경용 도커 이미지 빌드 중..."
docker build -f Dockerfile.offline -t anomaly-toolkit:offline .

# 2. 도커 이미지를 tar 파일로 저장
echo "도커 이미지 패키징 중..."
docker save -o anomalytoolkit.tar anomaly-toolkit:offline

# 3. 배포 패키지 폴더 생성
echo "배포 패키지 생성 중..."
mkdir -p offline-package
cp docker-compose.offline.yml offline-package/docker-compose.yml
cp anomalytoolkit.tar offline-package/
mkdir -p offline-package/media offline-package/logs

# 4. 설치 스크립트 생성
cat > offline-package/setup.sh << 'EOF'
#!/bin/bash
# macOS/Linux용 설치 스크립트

echo "LOGSCO 이상 로그 탐지 서비스 설정 중..."

# 환경 변수 파일 생성
if [ ! -f .env ]; then
    echo "환경 변수 파일 생성 중..."
    SECRET_KEY=$(cat /dev/urandom | LC_CTYPE=C tr -dc 'a-zA-Z0-9' | fold -w 50 | head -n 1)
    echo "SECRET_KEY=$SECRET_KEY" > .env
fi

# 도커 이미지 로드
echo "도커 이미지 로딩 중... (잠시 시간이 소요될 수 있습니다)"
docker load -i anomalytoolkit.tar

echo "설정 완료! 다음 명령어로 서비스를 시작하세요:"
echo "docker-compose up -d"
echo "브라우저에서 http://localhost:8000 으로 접속하세요."
EOF

# 5. 안내 문서 생성
cat > offline-package/README.txt << 'EOF'
==== LOGSCO 이상 로그 탐지 서비스 망분리 환경 실행 가이드 (macOS/Linux) ====

1. 설치 전 준비사항
   - Docker Desktop이 설치되어 있어야 합니다.
   - Terminal 접근 권한이 필요합니다.

2. 설치 및 실행 방법
   a. 이 폴더의 모든 파일을 대상 시스템에 복사합니다.
   b. Terminal을 열고 이 폴더로 이동합니다.
   c. 다음 명령어로 설치 스크립트에 실행 권한을 부여합니다:
      $ chmod +x setup.sh
   d. 설치 스크립트를 실행합니다:
      $ ./setup.sh
   e. 설정이 완료되면 다음 명령어로 서비스를 시작합니다:
      $ docker-compose up -d

3. 서비스 접속 방법
   - 웹 브라우저에서 http://localhost:8000 으로 접속합니다.
   - 업로드: http://localhost:8000/upload/
   - 대시보드: http://localhost:8000/dashboard/

4. 서비스 관리 명령어
   - 서비스 상태 확인: docker-compose ps
   - 로그 확인: docker-compose logs -f
   - 서비스 중지: docker-compose down
   - 서비스 재시작: docker-compose restart

5. 트러블슈팅
   - 서비스 실행 문제 발생 시 로그 확인: docker-compose logs -f
   - 데이터 초기화: docker-compose down -v (주의: 모든 데이터가 삭제됩니다)
EOF

# 6. 실행 권한 부여
chmod +x offline-package/setup.sh

# 7. 최종 zip 파일 생성
echo "최종 패키지 압축 중..."
cd offline-package
zip -r ../anomaly-toolkit-offline-mac.zip .
cd ..

echo "빌드 완료!"
echo "anomaly-toolkit-offline-mac.zip 파일이 생성되었습니다."
echo "이 파일을 망분리 환경에 복사하여 사용하세요."