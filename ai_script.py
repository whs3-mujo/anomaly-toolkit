# ai_script.py

import pandas as pd
from sklearn.preprocessing import StandardScaler
from pycaret.anomaly import setup, create_model, assign_model
import category_encoders as ce

def detect_anomalies(file_path):
    """
    업로드된 CSV 파일 경로(file_path)를 받아
    1) 전처리 → 2) PyCaret 이상 탐지 → 3) HTML 테이블 형태 결과 반환
    """

    # 1. 데이터 불러오기
    data = pd.read_csv(file_path, index_col=0).dropna()

    # 2. 숫자형 / 문자형 분리
    numeric_cols     = data.select_dtypes(include=['int64', 'float64']).columns
    categorical_cols = data.select_dtypes(include=['object']).columns

    # 3. Frequency Encoding
    encoder = ce.CountEncoder()
    data_encoded = encoder.fit_transform(data[categorical_cols])

    # 4. 합치기 + 스케일링
    full_data = pd.concat([
        data[numeric_cols].reset_index(drop=True),
        data_encoded .reset_index(drop=True)
    ], axis=1)
    scaler     = StandardScaler()
    data_scaled = pd.DataFrame(
        scaler.fit_transform(full_data),
        columns=full_data.columns
    )

    # 5. PyCaret 환경 설정 및 모델 생성
    exp   = setup(data_scaled, session_id=42, verbose=False, index=False)
    model = create_model('iforest')
    results = assign_model(model, score=True)

    # 6. 탐지 개수 집계
    count_anomaly = int(results['Anomaly'].sum())
    total         = len(results)

    # 7. 이상 탐지된 항목만 CSV로 저장 (원하면)
    detected = results[results['Anomaly'] == 1]
    detected.to_csv("pycaret_detected_anomalies.csv", index=False)

    # 8. 결과를 HTML 테이블 + 요약 문자열로 반환
    summary = f"<p>📌 이상치 {count_anomaly:,}건 / 전체 {total:,}건</p>"
    table_html = results.to_html(index=False, classes="table table-sm")

    return summary + table_html
