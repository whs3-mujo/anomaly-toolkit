==== LOGSCO 이상 로그 탐지 서비스 Apple Silicon 전용 오프라인 패키지 ====

🍎 Apple Silicon (M1/M2/M3) MacBook 최적화 버전
⚡ ARM64 네이티브 실행으로 최고 성능 보장

═══════════════════════════════════════════════════════════════════

📋 설치 및 실행 가이드

1️⃣ 사전 준비
   ✅ Docker Desktop for Mac 설치 필수
     - 다운로드: https://www.docker.com/products/docker-desktop
   ✅ 시스템 요구사항
     - macOS 12.0 (Monterey) 이상
     - Apple Silicon (M1/M2/M3) 전용
   ✅ 하드웨어: 최소 8GB RAM, 10GB 디스크 여유 공간

2️⃣ 설치 및 실행
   # 1. 압축 해제
   tar -xzf anomaly-toolkit-offline-macos-arm64.tar.gz
   cd anomaly-toolkit-offline-macos-arm64
   
   # 2. 권한 설정
   chmod +x *.sh
   
   # 3. 초기 설정 (최초 1회)
   ./setup.sh
   
   # 4. 서비스 시작
   ./start_service.sh
   
   # 5. 브라우저 접속
   http://localhost:8000/upload/
   http://localhost:8000/dashboard/

3️⃣ 서비스 접속 및 사용
   📁 파일 업로드: http://localhost:8000/upload/
   📊 분석 대시보드: http://localhost:8000/dashboard/
   
   💡 샘플 데이터를 업로드하여 테스트해보세요

4️⃣ 서비스 관리 및 데이터 보존
   시작: ./start_service.sh
   중지: ./stop_service.sh (데이터 보존됨)
   상태: docker ps
   로그: docker logs anomaly-detector
   
   📁 보존되는 데이터:
   • media/ - 업로드한 CSV 파일들
   • db_data/ - 분석 결과, 사용자 세션
   • logs/ - 서비스 실행 로그

5️⃣ 성능 최적화 특징
   🚀 Apple Silicon ARM64 네이티브 실행
   🔥 Rosetta 2 오버헤드 없음
   ⚡ M1/M2/M3 프로세서 최적화
   💾 효율적인 메모리 사용

6️⃣ 트러블슈팅
   문제상황 | 해결방법
   ──────────────────────────────────────────
   포트 8000 사용중 | sudo lsof -i :8000으로 확인 후 종료
   Docker 오류 | Docker Desktop 재시작
   권한 오류 | chmod +x *.sh 실행
   SECRET_KEY 오류 | ./setup.sh 재실행
   
   🔧 완전 초기화가 필요한 경우:
   docker stop anomaly-detector && docker rm anomaly-detector
   rm -rf media logs .env
   ./setup.sh

═══════════════════════════════════════════════════════════════════

💻 시스템 정보
- 최적화 대상: Apple Silicon (M1/M2/M3)
- 아키텍처: ARM64 네이티브
- 패키지 크기: 약 1.2GB (Docker 이미지 포함)
- 네트워크: 완전 오프라인 실행 가능

🆘 기술 지원
- GitHub: https://github.com/whs3-mujo/anomaly-toolkit
- 이슈 리포트: GitHub Issues

🏷️ 라이선스: MIT License
👥 개발팀: TEAM 이상無조

═══════════════════════════════════════════════════════════════════