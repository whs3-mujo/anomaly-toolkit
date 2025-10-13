# 🤝 Contributing to LOGSCO

LOGSCO에 기여해 주셔서 감사합니다!  
이 문서는 프로젝트에 기여하기 위한 기본 원칙과 절차를 안내합니다.

---

## 1. 기여 전 준비

1. **리포지토리 포크(Fork)**  
   - https://github.com/whs3-mujo/anomaly-toolkit 에서 본인 계정으로 Fork 후 clone

2. **브랜치 생성 규칙**
   - 기능 추가: `feature/<기능명>`  
   - 버그 수정: `fix/<이슈번호>`  
   - 문서 수정: `docs/<수정내용>`  
   - 예시:  
     ```bash
     git checkout -b feature/upload-threshold
     ```

3. **개발 환경 설정**
   - Python 3.11 권장  
   - 가상환경 생성 후 의존성 설치  
     ```bash
     virtualenv --python=3.11 .venv
     . .venv/bin/activate
     pip install -r requirements.txt
     ```

---

## 2. 커밋 규칙 (Conventional Commits)

커밋 메시지는 다음 형식을 따릅니다.

```
<type>: <description>
```

| Type | 설명 |
|------|------|
| `feat` | 새로운 기능 추가 |
| `fix` | 버그 수정 |
| `docs` | 문서 변경 (README, 주석 등) |
| `style` | 코드 포맷팅, 세미콜론 누락 등 |
| `refactor` | 코드 리팩토링 (기능 변경 없음) |
| `test` | 테스트 코드 추가/수정 |
| `chore` | 빌드, 패키지 관련 기타 작업 |

**예시**
```
feat: threshold 슬라이더 조정 기능 추가
fix: anomaly-score 컬럼 오류 수정
docs: 샘플 데이터 설명 보완
```

---

## 3. Pull Request (PR) 가이드

1. **PR 제목은 커밋 규칙을 따릅니다.**  
   예: `feat: upload threshold 설정 기능 추가`

2. **PR 설명 템플릿**
   ```
   ## 개요
   이번 PR의 목적 또는 주요 변경사항을 간단히 설명합니다.

   ## 변경 내용
   - [x] 주요 기능 추가
   - [x] 버그 수정
   - [ ] 테스트 코드 작성

   ## 테스트 방법
   - Docker 실행 후 http://localhost:8000 접속
   - 샘플 로그 업로드 시 threshold 기능 확인
   ```

3. **리뷰 전 체크리스트**
   - 코드가 정상적으로 실행되는지 테스트
   - Lint 및 포맷터 적용 (`black`, `prettier`)
   - 변경된 코드에 주석 및 문서 보완

---

## 4. 이슈 제보 (Issues)

새로운 기능 제안, 버그 리포트, 문서 개선 제안은  
GitHub [Issues 탭](https://github.com/whs3-mujo/anomaly-toolkit/issues)에 등록해주세요.

**이슈 템플릿 예시**
```
### 문제 요약
업로드 화면에서 threshold 값이 적용되지 않음

### 재현 절차
1. sample.csv 업로드
2. threshold 80% 설정
3. "분석 실행" 클릭 시 오류 발생

### 예상 동작
threshold 설정이 정상 반영되어야 함
```

---

## 5. 코드 리뷰 및 병합

- 모든 PR은 최소 1명 이상의 팀원이 리뷰 후 병합됩니다.
- `develop` 브랜치에 먼저 병합 후, `main`으로 릴리즈합니다.
- 긴급 패치의 경우 `fix/hotfix` 브랜치로 직접 반영할 수 있습니다.

---

## 6. 기타 참고 사항

- 모든 코드 변경은 자동화 테스트 통과를 권장합니다.
- 새로 추가된 기능은 README에 반드시 반영해주세요.
- 라이선스 및 외부 패키지 변경 시 `notice.txt` 업데이트를 잊지 마세요.

---

LOGSCO는 **AI 기반 이상탐지 플랫폼의 오픈소스 표준**을 지향합니다.  
여러분의 기여가 LOGSCO를 더 강력하게 만듭니다.  
감사합니다 💙
