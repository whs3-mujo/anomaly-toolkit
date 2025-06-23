import pandas as pd
from sklearn.preprocessing import StandardScaler
from pycaret.anomaly import *
import category_encoders as ce

# 1. 데이터 불러오기
data_path = "bok_logs_rule_3000.csv"
data = pd.read_csv(data_path, index_col=0).dropna()

# 2. 숫자형 / 문자형 분리
numeric_cols = data.select_dtypes(include=['int64', 'float64']).columns
categorical_cols = data.select_dtypes(include=['object']).columns

# 3. Frequency Encoding
encoder = ce.CountEncoder()
data_encoded = encoder.fit_transform(data[categorical_cols])

# 4. 합치기 + 스케일링
full_data = pd.concat([
    data[numeric_cols].reset_index(drop=True),
    data_encoded.reset_index(drop=True)
], axis=1)
scaler = StandardScaler()
data_scaled = pd.DataFrame(scaler.fit_transform(full_data), columns=full_data.columns)

# 5. PyCaret 환경 설정 및 모델 생성
exp = setup(data_scaled, session_id=42, verbose=False, index=False)
model = create_model('iforest')
results = assign_model(model, score=True)

# 6. 탐지 개수 출력
count_anomaly = results['Anomaly'].sum()
total = len(results)
print(f"\n📌 PyCaret이 이상치로 판단한 로그 개수: {count_anomaly:,}건 / 전체 {total:,}건")

# 7. 이상 탐지된 결과 저장
results_detected = results[results['Anomaly'] == 1]
results_detected.to_csv("pycaret_detected_anomalies.csv", index=False)
print(f"✅ PyCaret 이상치 탐지 결과 {len(results_detected)}건이 'pycaret_detected_anomalies.csv'에 저장되었습니다.")