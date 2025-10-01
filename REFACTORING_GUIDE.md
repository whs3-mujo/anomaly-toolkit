# Anomaly Detection Toolkit - 리팩토링 가이드

## 🔄 리팩토링된 모듈화 구조

이 프로젝트는 오픈소스 배포를 위해 모듈화된 아키텍처로 리팩토링되었습니다.

### 📁 새로운 디렉토리 구조

```
web/
├── core/                    # 핵심 모듈
│   ├── __init__.py         # 버전 정보
│   ├── config.py           # 설정 관리
│   └── exceptions.py       # 사용자 정의 예외
├── pipelines/              # 데이터 처리 파이프라인
│   ├── __init__.py
│   ├── preprocessing.py    # 데이터 전처리
│   └── detection.py        # 이상 탐지 모델
├── services/               # 비즈니스 로직
│   ├── __init__.py
│   ├── file_service.py     # 파일 처리
│   └── analysis_service.py # 분석 서비스
├── ai_script.py           # 메인 인터페이스 (하위 호환성)
├── ai_script_old.py       # 기존 버전 (백업)
└── ... (기타 파일들)
```

## 🚀 주요 개선 사항

### 1. 모듈화 및 관심사 분리
- **Core 모듈**: 설정, 예외 처리, 기본 구성
- **Pipeline 모듈**: 데이터 전처리, 모델 학습/예측
- **Service 모듈**: 파일 처리, 분석 비즈니스 로직

### 2. 설정 관리 개선
- 환경 변수 기반 설정 관리
- 개발/운영 환경별 설정 분리
- `.env` 파일 지원

### 3. 오류 처리 강화
- 사용자 정의 예외 클래스
- 구체적인 오류 메시지
- 적절한 fallback 처리

### 4. 타입 힌트 및 문서화
- 모든 함수에 타입 힌트 추가
- Docstring으로 함수 문서화
- 코드 가독성 향상

## 🔧 사용 방법

### 기존 API 호환성
기존 코드는 변경 없이 동작합니다:

```python
from web.ai_script import detect_anomalies

result = detect_anomalies(
    file_path="data.csv",
    exclude_columns=["id"],
    user_col="user",
    time_col="timestamp"
)
```

### 새로운 모듈화된 방식
더 세밀한 제어가 필요한 경우:

```python
from web.services.analysis_service import AnalysisService
from web.core.config import config

# 설정 변경
config.model.contamination = 0.1

# 분석 실행
service = AnalysisService()
result = service.run_complete_analysis(
    file_path="data.csv",
    exclude_columns=["id"],
    user_col="user",
    time_col="timestamp"
)
```

## ⚙️ 환경 설정

### 1. 환경 변수 파일 생성
```bash
cp .env.example .env
# .env 파일을 편집하여 필요한 설정 변경
```

### 2. 주요 설정 옵션

| 변수명 | 기본값 | 설명 |
|--------|--------|------|
| `MODEL_CONTAMINATION` | 0.05 | 이상치 비율 |
| `MODEL_RANDOM_STATE` | 42 | 랜덤 시드 |
| `TFIDF_MAX_FEATURES` | 100 | TF-IDF 최대 특성 수 |
| `UI_DEFAULT_THRESHOLD` | -0.20 | 기본 임계값 |
| `UPLOAD_TIMEOUT` | 600 | 업로드 타임아웃(초) |

## 🧪 테스트

### 기본 동작 테스트
```python
# 기존 방식으로 테스트
from web.ai_script import detect_anomalies

# 새로운 방식으로 테스트
from web.services.analysis_service import AnalysisService
```

### 설정 테스트
```python
from web.core.config import config

print(f"Model contamination: {config.model.contamination}")
print(f"UI threshold: {config.ui.default_threshold}")
```

## 📊 성능 개선

### 1. 메모리 사용량 최적화
- SHAP 계산 시 데이터 크기 제한
- TF-IDF 특성 수 동적 조절
- 불필요한 중간 데이터 정리

### 2. 처리 속도 향상
- 배치 처리 최적화
- 캐싱 메커니즘 (필요시)
- 병렬 처리 지원 (향후 계획)

## 🔍 디버깅 및 로깅

### 디버그 모드 활성화
```bash
# .env 파일에서
ENABLE_DEBUG=true
LOG_LEVEL=DEBUG
```

### 상세한 로그 출력
모든 주요 단계에서 진행 상황이 출력됩니다:
- 🔍 분석 시작
- 📁 파일 처리
- 🔄 데이터 전처리
- 🤖 모델 학습
- 📊 결과 생성

## 🚧 향후 개선 계획

1. **테스트 코드 추가**: pytest 기반 단위 테스트
2. **API 문서화**: Swagger/OpenAPI 문서 생성
3. **성능 모니터링**: 실행 시간 및 리소스 사용량 추적
4. **플러그인 시스템**: 사용자 정의 모델 추가 지원
5. **실시간 분석**: 스트리밍 데이터 처리 지원

## 📝 마이그레이션 가이드

### 기존 코드에서 새 구조로 마이그레이션

1. **설정 분리**:
   ```python
   # 기존
   def detect_anomalies(contamination=0.05, ...):
   
   # 새로운 방식
   from web.core.config import config
   config.model.contamination = 0.05
   ```

2. **예외 처리 개선**:
   ```python
   # 기존
   try:
       result = detect_anomalies(...)
   except Exception as e:
       print(f"Error: {e}")
   
   # 새로운 방식
   from web.core.exceptions import AnomalyDetectionError
   try:
       result = detect_anomalies(...)
   except AnomalyDetectionError as e:
       print(f"Analysis error: {e}")
   ```

3. **모듈별 접근**:
   ```python
   # 전처리만 필요한 경우
   from web.pipelines.preprocessing import DataPreprocessor
   
   # 파일 처리만 필요한 경우
   from web.services.file_service import FileService
   ```

## 💡 기여 가이드

1. 새로운 기능은 적절한 모듈에 추가
2. 타입 힌트와 docstring 필수
3. 기존 API 호환성 유지
4. 단위 테스트 작성 권장

---

이 리팩토링을 통해 코드의 유지보수성, 확장성, 테스트 용이성이 크게 향상되었습니다.