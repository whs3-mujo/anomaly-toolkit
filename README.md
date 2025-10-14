<!-- LOGSCO HEADER -->
![LOGSCO Header](./docs/images/header.png)

[![license](https://img.shields.io/badge/license-MIT-ff4081.svg?style=flat-square&labelColor=black)](./LICENSE)
[![python](https://img.shields.io/badge/python-3.11-blue.svg?style=flat-square&labelColor=black&logo=python&logoColor=white)](https://www.python.org/)
[![docker](https://img.shields.io/badge/docker-ready-2496ED.svg?style=flat-square&labelColor=black&logo=docker&logoColor=white)](https://www.docker.com/)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-ffab00.svg?style=flat-square&labelColor=black)](https://conventionalcommits.org)
![PRs welcome](https://img.shields.io/badge/PRs-welcome-09FF33.svg?style=flat-square&labelColor=black)

---

# LOGSCO  
**AI 기반 이상로그 탐지 서비스 (AI-Powered Log Scoring & Analysis System)**  

스마트 로그 분석과 이상 탐지를 자동화하는 오픈소스 툴킷입니다.  
[시연 영상 보기](https://www.youtube.com/playlist?list=PLJOyfcewGGvYWiry_4vStBUEzOWpJ6w07)

---

## 1. LOGSCO 소개  

**LOGSCO**는 대규모 보안 로그에서 **AI 기반 이상 패턴을 자동 탐지**하는 플랫폼입니다.  
데이터 흐름을 “점과 선(노드와 관계)”로 파악하여,  
복잡한 로그 안에서도 비정상 행위를 직관적으로 찾아냅니다.  

> LOGSCO의 목표는 단순한 탐지가 아닌,  
> **‘데이터의 연결 관계 속에서 이상을 이해하는 것’** 입니다.

---

## 2. 로고의 의미  

| 구성요소 | 의미 |
|-----------|------|
| 파란색 원 | 신뢰·보안·데이터의 안정성을 상징하며, LOGSCO의 분석 범위를 표현 |
| 노드 + 연결선 | 로그 이벤트 간 상관관계, AI가 학습하는 데이터 흐름의 시각화 |
| 원형 구조 | 폐쇄된 보안 경계와 자율 탐지 시스템의 완결성 상징 |

> LOGSCO는 **데이터의 연결을 이해하고, 관계 속에서 비정상을 감지하는 AI 시스템**을 의미합니다.

🔗 [LOGSCO 아이콘](./docs/images/icon.png)

---

## 3. 주요 기능  

- PyCaret 기반 **AI 이상탐지 자동화**
- **Threshold 직접 설정 기능** (사용자 맞춤 조정)
- Plotly 기반 **이상치 시각화 그래프**
- **Docker 완전 지원**, 1분 내 실행 가능
- **온프레미스(오프라인)** 환경 지원  

> ⚙️ **업로드 제한 안내**  
> - 기본적으로 5분 이하의 로그 데이터만 업로드 가능합니다.  
> - 더 큰 데이터는 [GitHub Issue](https://github.com/whs3-mujo/anomaly-toolkit/issues)를 통해 문의해주세요.  
>   (기술적으로 가능하지만, 서비스 효율성을 위해 제한되어 있습니다.)

---

## 4. 샘플 데이터  

**파일명:** [Final_Fintech_Security_Logs.csv](https://raw.githubusercontent.com/whs3-mujo/anomaly-toolkit/main/samples/Final_Fintech_Security_Logs.csv)<br />
**설명:** 실제 금융기관 로그 환경 기반의 보안 로그 샘플

| 컬럼명 | 설명 |
|--------|------|
| timestamp | 로그 발생 시각 |
| user_id | 사용자 식별자 |
| event_type | 이벤트 유형 |
| ip_address | 접속 IP 주소 |
| process_name | 실행된 프로세스 이름 |
| anomaly_score | AI 이상치 점수 |

**사용 예시**
```bash
python manage.py runserver
# 웹 대시보드 접속 후 Final_Fintech_Security_Logs.csv 업로드
```

---

## 5. Docker 실행 가이드  

### 1) Docker 설치  
[Docker Desktop 다운로드](https://www.docker.com/products/docker-desktop)

### 2) 버전 확인  
```bash
docker --version
docker compose version
```

### 3) 이미지 다운로드  
```bash
docker pull ynjii/anomaly-toolkit:latest
```

### 4) 환경 설정  
```bash
mkdir logscope && cd logscope
```

`docker-compose.yml` 작성
```yaml
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

`.env` 작성
```bash
SECRET_KEY="django-insecure-abc123456789"
```

**새 SECRET_KEY 발급**
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 5) 실행  
```bash
docker compose up -d
```

**접속 경로**
- 업로드: http://localhost:8000/upload  
- 대시보드: http://localhost:8000/dashboard  

---

## 6. 개발자 환경 세팅  

```bash
# 1. 가상환경 생성
virtualenv --python=3.11 .venv
. .venv/bin/activate

# 2. 의존성 설치
pip install -r requirements.txt

# 3. 마이그레이션
python manage.py makemigrations
python manage.py migrate

# 4. 관리자 계정 생성
python manage.py createsuperuser

# 5. SECRET_KEY 등록
export SECRET_KEY=[비밀키]

# 6. 서버 실행
python manage.py runserver 0.0.0.0:8000
```

---

## 7. 팀 구성  

| 이름 | 역할 | GitHub |
|------|------|---------|
| 김윤지 | 웹 베이스코드 | [@ynjii](https://github.com/ynjii) |
| 김지윤 | XAI 및 그래프 시각화 / DevOps | [@JIYUN02](https://github.com/JIYUN02) |
| 백형철 | XAI 및 그래프 시각화 | [@BAEK10000](https://github.com/BAEK10000) |
| 심준호 | XAI 및 그래프 시각화 | [@junho462](https://github.com/junho462) |
| 이준혁 | XAI 및 그래프 시각화 | [@hubkorea](https://github.com/hubkorea) |
| 정원재 | AI 모델 개발 | [@daljoa](https://github.com/daljoa) |
| 정채윤 | AI 모델 개발 | [@jcy333](https://github.com/jcy333) |
| 최아현 | AI 모델 개발 | [@ChoiAh](https://github.com/ChoiAh) |

---

## 8. 기여 (Contributing)

LOGSCO 프로젝트에 기여하려면 아래 절차를 따르세요.

```bash
# 1. 포크 후 브랜치 생성
git checkout -b feature/새기능명

# 2. 코드 수정 및 커밋
git commit -m "feat: 새 기능 요약"

# 3. PR 생성
git push origin feature/새기능명
```

**PR 규칙**
- 제목은 *Conventional Commit* 규칙을 따릅니다.  
- 예: `fix: threshold 슬라이더 오류 수정`  
- 자세한 가이드는 [`CONTRIBUTING.md`](./docs/CONTRIBUTING.md) 참고

---

## 9. 오픈소스 라이선스  

### 메인 라이선스  

본 프로젝트는 **MIT License** 하에 배포됩니다.  
© 2025 TEAM LOGSCO  
모든 사용자는 자유롭게 이용·수정·배포할 수 있으며,  
원 저작권 표기와 라이선스 전문을 포함해야 합니다.  
소프트웨어는 **보증 없이 "있는 그대로(AS IS)" 제공**됩니다.  
[전체 전문 보기](./docs/LICENSE)

---

### 포함된 외부 라이브러리  

LOGSCO는 다음 오픈소스 라이브러리들을 포함합니다.  
세부 정보는 [`notice.txt`](./docs/notice.txt)에서 확인할 수 있습니다.

| 라이브러리 | 버전 | 라이선스 | 비고 |
|-------------|-------|-----------|------|
| Django | 5.2.7 | BSD 3-Clause | 웹 프레임워크 |
| gunicorn | 23.0.0 | MIT | WSGI 서버 |
| python-dotenv | 1.1.1 | BSD 3-Clause | 환경변수 관리 |
| pandas | 2.3.3 | BSD 3-Clause | 데이터 처리 |
| scikit-learn | 1.7.2 | BSD 3-Clause | ML 알고리즘 |
| numpy | 2.3.3 | BSD 3-Clause | 수치 계산 |
| pyod | 2.0.5 | BSD 2-Clause | 이상탐지 모델 |
| shap | 0.48.0 | MIT | 모델 해석용 |
| plotly | 6.3.1 | MIT | 시각화 라이브러리 |
| chardet | 5.2.0 | LGPL 2.1-or-later | 인코딩 탐지기 |
| category-encoders | 2.81 | BSD 3-Clause | 데이터 전처리 |
| joblib | 1.5.2 | BSD 3-Clause | 병렬처리 유틸리티 |

> **참고:** LGPL(예: chardet) 기반 모듈은  
> 사용자가 교체 가능한 형태로 제공되어야 합니다.

---

## 10. License Summary  

- **Main Project:** MIT License (TEAM LOGSCO)  
- **Sub Libraries:** BSD, MIT, LGPL (see notice.txt)  
- **Distribution:** 자유로운 사용/수정/상용 배포 가능  
- **Obligation:** 원저작권 표시 및 notice 파일 포함 필수  

---

### LOGSCO — 로그에서 인사이트로  
AI와 함께, 더 똑똑한 로그 보안을 경험하세요.
