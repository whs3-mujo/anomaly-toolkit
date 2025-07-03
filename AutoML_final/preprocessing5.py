import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.feature_extraction.text import TfidfVectorizer
import category_encoders as ce
from pycaret.anomaly import setup, create_model, assign_model
from sklearn.metrics import classification_report, confusion_matrix
# 텍스트 컬럼 탐지 함수
def detect_text_columns(df, min_avg_length=20):
    candidate_cols = df.select_dtypes(include=['object', 'string']).columns
    text_cols = []
    for col in candidate_cols:
        if df[col].apply(lambda x: isinstance(x, str)).all():
            if df[col].astype(str).apply(len).mean() >= min_avg_length:
                text_cols.append(col)
    return text_cols

# 전처리 함수
def preprocess_log_data_with_text(df, 
                                   encode_method='count', 
                                   scale=True,
                                   tfidf_max_features=100):
    # 숫자형
    numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns.tolist()

    # 텍스트형
    text_cols = detect_text_columns(df)

    # 범주형 (텍스트 컬럼 제외)
    categorical_cols = df.select_dtypes(include=['object', 'category', 'bool']).columns
    categorical_cols = [col for col in categorical_cols if col not in text_cols]

    # 인코딩
    if categorical_cols:
        if encode_method == 'count':
            encoder = ce.CountEncoder()
            encoded = encoder.fit_transform(df[categorical_cols])
        else:
            raise ValueError("지원되지 않는 인코딩 방식입니다.")
    else:
        encoded = pd.DataFrame(index=df.index)

    # TF-IDF
    tfidf_vectorizer = TfidfVectorizer(max_features=tfidf_max_features)
    tfidf_df_list = []
    for col in text_cols:
        tfidf_matrix = tfidf_vectorizer.fit_transform(df[col].astype(str).fillna(''))
        tfidf_df = pd.DataFrame(tfidf_matrix.toarray(), columns=[f"{col}_tfidf_{i}" for i in range(tfidf_matrix.shape[1])])
        tfidf_df_list.append(tfidf_df)
    tfidf_combined = pd.concat(tfidf_df_list, axis=1) if tfidf_df_list else pd.DataFrame(index=df.index)

    # 결합
    df_numeric = df[numeric_cols].reset_index(drop=True)
    df_encoded = encoded.reset_index(drop=True)
    tfidf_combined = tfidf_combined.reset_index(drop=True)
    final_data = pd.concat([df_numeric, df_encoded, tfidf_combined], axis=1)

    # 스케일링
    if scale:
        scaler = StandardScaler()
        final_data = pd.DataFrame(scaler.fit_transform(final_data), columns=final_data.columns)

    info = {
        'numeric_cols': numeric_cols,
        'categorical_cols': categorical_cols,
        'text_cols': text_cols,
        'final_shape': final_data.shape
    }

    return final_data, info

# 메인 실행
# 1. 데이터 불러오기
data_path = "synthetic_log_data.csv"
data = pd.read_csv(data_path, index_col=0).dropna()
# 라벨 불러오기 (0: 정상, 1: 이상)
labels = pd.read_csv("synthetic_label.csv")#['Class']
# 2. 전처리 수행
processed_data, info = preprocess_log_data_with_text(data)

# 3. PyCaret 이상 탐지
exp = setup(processed_data, session_id=42, verbose=False, index=False)
model = create_model('iforest')
results = assign_model(model, score=True)

# 4. 결과 출력
count_anomaly = results['Anomaly'].sum()
total = len(results)
print("\n 전처리 결과:")
print(f" - 숫자형: {info['numeric_cols']}")
print(f" - 범주형: {info['categorical_cols']}")
print(f" - 텍스트: {info['text_cols']}")
print(f" - 전처리된 shape: {info['final_shape']}")

print(f"\n PyCaret이 이상치로 판단한 로그 개수: {count_anomaly:,}건 / 전체 {total:,}건")

# 5. 결과 저장
results_detected = results[results['Anomaly'] == 1]
results_detected.to_csv("pycaret_detected_anomalies(2).csv", index=False)
print(f" 이상치 {len(results_detected)}건이 'pycaret_detected_anomalies(2).csv'에 저장되었습니다.")

# 6. 이상치 결과를 실제 라벨과 비교
# PyCaret은 Anomaly 컬럼에서 1은 이상치, 0은 정상으로 간주
predicted = results['Anomaly']
true = labels.reset_index(drop=True)


# . 평가 지표 출력
print("Confusion Matrix:")
print(confusion_matrix(true, predicted))
print("\nClassification Report:")
print(classification_report(true, predicted, target_names=["정상", "이상"]))
