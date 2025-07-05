# Anomaly-Toolkit

## 개요
본 도구는 화이트햇스쿨 프로젝트로 개발한 AI 기반 로그 이상 탐지 도움 툴킷입니다.

## 요구사항

### 실행 환경(보안 담당자)
- docker, docker-compose 필요

### 개발 환경(개발자)
- python 3.10, or 3.11 필요 (pycarat의 경우 3.12 이상 현재 미지원)
- virtualenv 필요 (`pip install virtualenv`)

## 사용법

### 실행 및 사용(보안 담당자)

- 이미지 빌드, 컨테이너 실행
```bash
# 1. 빌드하여 도커 이미지 생성
$ docker-compose build --no-cache

# 2. 환경변수 파일 생성
# 'manage.py'가 있는 경로에 '.env' 파일 만들기
# 파일 내용은 다음과 같이 작성하고 저장(예시이며 비밀키로 사용할 문자열 직접 입력)
SECRET_KEY=123

# 3. 생성된 도커 이미지를 컨테이너로 실행(백그라운드 옵션)
$ docker-compose up -d
```
- 사용 Flow
  1. 브라우저 - `http://127.0.0.1:8000/` 접근 확인
  2. 'http://127.0.0.1:8000/upload/` 접근
  3. 로그 업로드(example.csv 제공)
  4. 대시보드에서 결과 확인

- 컨테이너 종료
```bash
# 컨테이너 종료
$ docker-compose down
```

### 초기 개발 환경 세팅(개발자)


```bash
# 가상환경 세팅
$ virtualenv --python=3.11 .venv
$ . .venv/bin/activate
# 의존성 파이썬 라이브러리 설치
(.venv) $ pip install -r requirements.txt
# 장고 - 모델의 변경사항 확인 후 마이그레이션 파일로 기록
(.venv) $ python manage.py makemigrations
# 장고 - 생성된 마이그레이션 파일을 읽어 DB에 실제 적용
(.venv) $ python manage.py migrate
# 장고 - admin 계정 생성(email 생략 가능)
(.venv) $ python manage.py createsuperuser
# 장고 - 암호화 서명에 사용되는 비밀키 환경변수 지정
(.venv) $ export SECRET_KEY=[비밀키 지정]
# 장고 - 서버 실행
(.venv) $ python manage.py runserver 0.0.0.0:8000
```
브라우저 - `http://127.0.0.1:8000/` 접근 확인

