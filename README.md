# LOGSCO: AI기반 이상로그 탐지서비스

## 개요
본 도구는 AI 기반 로그 이상 탐지 도움 툴킷입니다. <br />
[**시연 영상**](https://www.youtube.com/watch?v=6EWizN8p7mI&list=PLJOyfcewGGvYWiry_4vStBUEzOWpJ6w07)

## 요구사항
### 실행 환경
- docker, docker-compose 필요

### 개발 환경
- python 3.10, or 3.11 필요 (pycaret의 경우 3.12 이상 현재 미지원)
- virtualenv 필요 (`pip install virtualenv`)
<br />

## 사용법
### Docker 실행 (간소화 버전)
1. [Docker Desktop 설치](https://www.docker.com/products/docker-desktop)
```bash
2. 터미널에서 설치 확인
$ docker --version
$ docker compose version

3. Docker Hub 로그인(최초 1회)
$ docker login

4. 이미지 다운로드
$ docker pull ynjii/anomaly-toolkit:latest
	#오프라인 환경 실행 버전(테스트 중 - plotly 그래프 미출력 오류)
	$ docker pull ynjii/anomlay-toolkit:offline (docker-compose.yml 내용 다름)

5. 실행 폴더 생성
$ mkdir 폴더명
$ cd 폴더명
```
<br />

6. docker-compose.yml 작성
해당 폴더 안에 아래 내용으로 docker-compose.yml 파일 생성
```bash
version: '3.8'
services:
  web:
    image: ynjii/anomaly-toolkit:latest
    container_name: anomalytoolkit-web
    ports:
      - "8000:8000"
    env_file:
      - .env
```
<br />

7. '.env' 파일 작성
같은 폴더에 .env 파일을 만들고 아래 내용 입력
```bash
SECRET_KEY="이 부분에 시크릿키값 입력"
```
<br />

 ※ 아래 명령어로 새 SECRET_KEY를 발급해 사용할 수 있습니다.
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())

출력 예시)django-insecure-abc123456789
```
<br />

8. 실행
```bash
$ docker compose up -d
#업로드: http://localhost:8000/upload/ 대시보드: http://localhost:8000/dashboard/
```
<br />

9. 상태 확인
```bash
docker compose ps         # 실행 상태 확인
docker compose logs -f    # 로그 보기
docker compose down       # 종료
```
### Docker 실행 (오프라인)
본 프로젝트는 온프레미스 및 망분리 환경에서도 실행할 수 있도록 오프라인 배포 패키지를 제공합니다.

#### 오프라인 패키지 사용 방법 (사용자용)
1. 제공된 오프라인 패키지 파일(`logsco-anomaly-detector.zip`)을 다운로드합니다.

2. ZIP 파일을 압축 해제합니다.

3. 운영체제에 맞는 시작 스크립트를 실행합니다:
   - Windows: `start_service.bat` 파일을 더블클릭
   - macOS/Linux: 터미널에서 `chmod +x start_service.sh` 실행 후 `./start_service.sh` 실행

4. 웹 브라우저에서 http://localhost:8000 으로 접속하여 서비스를 사용합니다:
   - 로그 파일 업로드: http://localhost:8000/upload/
   - 분석 결과 확인: http://localhost:8000/dashboard/

5. 서비스를 종료하려면:
   - Windows: `stop_service.bat` 파일을 더블클릭
   - macOS/Linux: `./stop_service.sh` 실행

#### 오프라인 패키지 제작 방법 (개발자용)
오프라인 패키지를 만들기 위해 다음 스크립트를 사용합니다:

```powershell
# PowerShell에서 실행
.\create_offline_package.ps1
```

이 스크립트는 도커 이미지를 빌드하고 tar 파일로 저장한 후, 사용자가 쉽게 서비스를 시작/중지할 수 있는 스크립트와 함께 배포 패키지를 생성합니다.

4. 웹 브라우저에서 http://localhost:8000 으로 접속하여 서비스를 사용합니다.
   (업로드: http://localhost:8000/upload/, 대시보드: http://localhost:8000/dashboard/)
<br />

### 초기 개발 환경 세팅 (개발자)
```bash
1. 가상환경 세팅
(맥 OS 환경) 
$ virtualenv --python=3.11 .venv
$ . .venv/bin/activate

(윈도우 환경 - powershell) 
$ python -m venv venv
$ .\venv\Scripts\Activate.ps1

2. 의존성 파이썬 라이브러리 설치
(.venv) $ pip install -r requirements.txt

3. 장고 - 모델의 변경사항 확인 후 마이그레이션 파일로 기록
(.venv) $ python manage.py makemigrations

4. 장고 - 생성된 마이그레이션 파일을 읽어 DB에 실제 적용
(.venv) $ python manage.py migrate
4.1. 장고 - DB적용 오류 발생 시 (1)~(3) 입력 후 재실행(히스토리 조회 불가, 대시보드 조회 불가 등)
(1) python manage.py makemigrations web
(2) python manage.py migrate web 
(3) python manage.py runserver  

5. 장고 - admin 계정 생성(email 생략 가능)
(.venv) $ python manage.py createsuperuser

6. 장고 - 암호화 서명에 사용되는 비밀키 환경변수 지정
(.venv) $ export SECRET_KEY=[비밀키 지정]

7. 장고 - 서버 실행
(.venv) $ python manage.py runserver 0.0.0.0:8000
7.1. 서버 실행 오류 발생 시 
(.venv) $ python manage.py runserver
```
---
## 운영체제별(WINDOWS, MAC) 가이드북
- [Windows](https://www.notion.so/2425227467f780bb8b9cc9c0c159a368?source=copy_link)
- [Mac](https://www.notion.so/2420363bd07c807191bde6b6acfee091?source=copy_link)

## Open Source Acknowledgement
본 프로젝트는 다음 오픈소스를 활용하였습니다:
- [PyCaret](https://github.com/pycaret/pycaret) (MIT License)
- [Plotly](https://github.com/plotly/plotly.py) (MIT License)

