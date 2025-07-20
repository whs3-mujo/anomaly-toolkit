# ai_script.py
#이제 행 개수 맞추기 하고, 사용자 그래프랑 xai랑 왜 안 맞는지 확인하고.. 끝.
import pandas as pd
from sklearn.preprocessing import StandardScaler
from pycaret.anomaly import setup, create_model, assign_model
import category_encoders as ce
import chardet ###수정하면서 추가한 부분
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer ###수정하면서 추가한 부분
import numpy as np
import shap
from .restore import restore_and_save_readable_anomalies
from .visualize_graph import (
    detect_user_and_time_columns,
    plot_anomaly_by_hour,
    plot_anomaly_by_user,
    plot_anomaly_score_distribution
)
def generate_description(df, user_col, time_col):
    import pandas as pd
    from collections import Counter

    # 1. 시간대 분류
    def time_to_period(hour):
        if 0 <= hour < 6:
            return "새벽시간(00-05시)"
        elif 6 <= hour < 12:
            return "오전시간(06-11시)"
        elif 12 <= hour < 18:
            return "오후시간(12-17시)"
        else:
            return "저녁시간(18-23시)"

    df = df.copy()
    df["hour"] = pd.to_datetime(df[time_col]).dt.hour
    df["period"] = df["hour"].apply(time_to_period)
    period_counts = df["period"].value_counts().to_dict()

    # 2. 사용자별 이상 로그 수
    user_counts = Counter(df[user_col])
    total = len(df)

    top_users = user_counts.most_common(5)
    top_summary = ", ".join([f"{u}: {c}건 ({c/total:.1%})" for u, c in top_users])
    top_total = sum([c for _, c in top_users])
    top_ratio = f"{top_total}건({top_total/total:.1%})"

    # 3. HTML 생성
    items = [item.strip() for item in top_summary.split(',') if item.strip()]

    formatted_top_summary = "<br>".join([
        f"{user}: <b><span style='color:red;'>{count}</span></b>"
        for user, count in (item.split(': ', 1) for item in items)
    ])

    html = f"""
    <div style='background:#e3f2fd; border-left:4px solid #2196f3; padding:1rem; margin-top:2rem;'>
    <h3 style='margin-top:0;'>종합 평가</h3>
    <div style='margin-bottom:1rem;'>
        <b>&lt;시간대별 이상 로그 분포&gt;</b><br>
        {"<br>".join([
            f"{k}: <b><span style='color:red;'>{v}건</span></b>"
            for k, v in sorted(period_counts.items())
        ])}<br>
        ➤ <b><span style='color:red;'>{max(period_counts, key=period_counts.get)}</b>에 가장 많은 이상 로그가 집중되어 있습니다.
    </div>
    <div>
        <b>&lt;상위 사용자 이상 로그 개수&gt;</b><br>
        {formatted_top_summary}<br>
        ➤ 상위 5명의 사용자가 전체 이상 로그 <b><span style='color:red;'>{total}건</span></b> 중 <b style='color:red;'>{top_ratio}</b>을 차지합니다.
    </div>
    </div>
    """
    return html



# 텍스트 컬럼 탐지
def detect_text_columns(df, min_avg_length=20):
    candidate_cols = df.select_dtypes(include=['object', 'string']).columns
    return [col for col in candidate_cols if df[col].astype(str).apply(len).mean() >= min_avg_length]

# 전처리 함수
def preprocess_log_data_with_text(df, encode_method='count', scale=True, tfidf_max_features=100):
    encoder = None  #추가
    numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns.tolist()
    text_cols = detect_text_columns(df)
    categorical_cols = df.select_dtypes(include=['object', 'category', 'bool']).columns
    categorical_cols = [col for col in categorical_cols if col not in text_cols]

    # 범주형 변수 인코딩 (CountEncoder 사용)
    if categorical_cols:
        if encode_method == 'count':
            encoder = ce.CountEncoder()
            encoded = encoder.fit_transform(df[categorical_cols])
        else:
            raise ValueError("지원되지 않는 인코딩 방식입니다.")
    else:
        encoded = pd.DataFrame(index=df.index)
    
    # 텍스트 데이터 TF-IDF 처리
    tfidf_vectorizer = TfidfVectorizer(max_features=tfidf_max_features)
    tfidf_df_list = []
    for col in text_cols:
        tfidf_matrix = tfidf_vectorizer.fit_transform(df[col].astype(str).fillna(''))
        tfidf_df = pd.DataFrame(tfidf_matrix.toarray(), columns=[f"{col}_tfidf_{i}" for i in range(tfidf_matrix.shape[1])])
        tfidf_df_list.append(tfidf_df)
    tfidf_combined = pd.concat(tfidf_df_list, axis=1) if tfidf_df_list else pd.DataFrame(index=df.index)

    # 숫자형, 인코딩된 범주형, TF-IDF 특성 결합
    df_numeric = df[numeric_cols].reset_index(drop=True)
    df_encoded = encoded.reset_index(drop=True)
    tfidf_combined = tfidf_combined.reset_index(drop=True)
    final_data = pd.concat([df_numeric, df_encoded, tfidf_combined], axis=1)  #, tfidf_combined

    # 스케일링
    if scale:
        scaler = StandardScaler()
        final_data = pd.DataFrame(scaler.fit_transform(final_data), columns=final_data.columns)


    return final_data, categorical_cols, encoder #info 주석처리 + cateforical_cols반환(밑에서 네임인식 안되는 거 같아서)


def detect_anomalies(file_path, exclude_columns=None, user_col=None, time_col=None):
    """
    업로드된 CSV 파일 경로(file_path)와 제외할 칼럼 리스트(exclude_columns)를 받아
    1) 전처리 → 2) PyCaret 이상 탐지 → 3) HTML 테이블 형태 결과 반환 """

    # 인코딩 자동 감지
    with open(file_path, 'rb') as f:
        raw_data = f.read(10000)  # 앞부분만 샘플로 추출
        result = chardet.detect(raw_data)
        detected_encoding = result['encoding']

    # 1. 데이터 불러오기, 결측치 제거
    data = pd.read_csv(file_path, encoding=detected_encoding)  # index_col=0 제거!
    data = data.dropna(axis=1, thresh=int(len(data)*0.7))  # 70% 이상 값 없는 열 제거

    # 제외할 칼럼이 있으면 제거📌📌전처리 함수 안으로 위치 옮김.
    if exclude_columns:
        data = data.drop(columns=[col for col in exclude_columns if col in data.columns])

    # 2. 전처리 수행 (스케일링 포함, 사용자 컬럼은 따로 무시하지 않음 → 그대로 포함됨)  categorical_cols, encoder 추가
    processed_data, categorical_cols, encoder = preprocess_log_data_with_text(
        data,
        encode_method='count',
        scale=True,
        tfidf_max_features=100
    ) 
    # TF-IDF 컬럼 패턴으로 추출📌추가📌
    tfidf_cols = [col for col in processed_data.columns if col.startswith('message_tfidf_')]
    non_tfidf_features = [col for col in processed_data.columns if col not in tfidf_cols]
    # processed_data_no_tfidf = processed_data[non_tfidf_features]

    exp = setup(
        data=processed_data,  # 전처리된 데이터 그대로 사용 (사용자 컬럼 포함)
        session_id=42,
        ignore_features=user_col,  # 사용자 컬럼 무시 (모델 학습엔 안 쓰임) 다른 그래프 코드랑 합치면 될 듯.
        verbose=False,              #출력 제어 옵션
        index=False
    )

       # 복원용 원본 정보 백업 (예: user_id, timestamp 등)
    original_info = data[categorical_cols].reset_index(drop=True)

    model = create_model('iforest')
    results = assign_model(model, score=True)

    # 4. 결과 출력
    count_anomaly = results['Anomaly'].sum()
    total = len(results)
    print(f"\n PyCaret이 이상치로 판단한 로그 개수: {count_anomaly:,}건 / 전체 {total:,}건")

    # 원본 정보에서 인코딩된 컬럼들을 제거하고 합치기 📌📌📌📌📌📌📌📌📌📌📌  =>ai코드 꺼는 아님.
    encoded_columns = [col for col in categorical_cols if col in results.columns]  #categorical_for_encoding?을 categorical_cols로 바꿈.
    results_cleaned = results.drop(columns=encoded_columns, errors='ignore')  #=> 이거 왜 있는 거지?????? 밑에 쓰임.

     # 6. SHAP 그래프를 그리기 위한 파일 생성(1)
    model_path = file_path.replace('.csv', '_model.pkl')    # SHAP값 계산을 위해 모델을 pkl파일로 추출
    joblib.dump(model, model_path)
    shap_input_path = file_path.replace('.csv', '_X_for_shap.csv')  # SHAP값 계산을 위해 실제 탐지 모델에 입력값으로 넣었던 data_scaled를 _X_for_shap.csv파일로 저장
    processed_data.to_csv(shap_input_path, index=False)  #data_scaled를 processed_data로 바꿈.

    # 이상치 점수 컬럼명 통일
    if 'Anomaly_Score' not in results.columns and 'Anomaly_Score' in results.columns:
        results['Anomaly_Score'] = results['Anomaly_Score']
    elif 'Anomaly_Score' not in results.columns and 'Anomaly Score' in results.columns:
        results['Anomaly_Score'] = results['Anomaly Score']
    elif 'Anomaly_Score' not in results.columns and 'anomaly_score' in results.columns:
        results['Anomaly_Score'] = results['anomaly_score']

    # 복원한 문자열 컬럼을 결과에 다시 붙이기 (중복 컬럼 방지)
    results_with_info = pd.concat([results_cleaned, original_info], axis=1)


    # 5. 결과 저장📌
    # results_detected = results[results['Anomaly'] == 1]
    # results_with_info.to_csv("full_data_with_anomaly_info.csv", index=False)
    results_with_info = pd.concat([results_cleaned.drop(columns=tfidf_cols, errors='ignore'), original_info], axis=1)
    results_with_info.to_csv("full_data_with_anomaly_info.csv", index=False)

    if encoder is not None:
        restore_and_save_readable_anomalies(
        anomaly_csv_path="full_data_with_anomaly_info.csv",
        encoder_mapping_dict=encoder.mapping,
        output_path="full_data_with_anomaly_info_readable.csv"
    )
        output_path = "full_data_with_anomaly_info_readable.csv"
    else:
        print("Encoder가 없어서 복원 단계 스킵")
        output_path = "full_data_with_anomaly_info.csv"


    # 전체 결과 복원 (문자열 컬럼) 📌위에꺼로 수정.
    # restore_and_save_readable_anomalies(
    #     anomaly_csv_path="full_data_with_anomaly_info.csv",
    #     encoder_mapping_dict=encoder.mapping,
    #     output_path="full_data_with_anomaly_info_readable.csv"
    # )

    # 복원된 전체 데이터 로드 📌
    df_full = pd.read_csv("full_data_with_anomaly_info_readable.csv")

    # 복원된 컬럼만 남기고, .1 붙은 컬럼명을 원래대로 변경 📌
    for col in df_full.columns:
        if col.endswith('.1'):
            orig_col = col[:-2]
            if orig_col in df_full.columns:
                df_full.drop(columns=[orig_col], inplace=True)
            df_full.rename(columns={col: orig_col}, inplace=True)

    # 사용자/시간 컬럼 자동 감지 (없으면 직접 입력) 📌
    if not user_col or not time_col:
        user_col_auto, time_col_auto = detect_user_and_time_columns(df_full)
        user_col = user_col or user_col_auto
        time_col = time_col or time_col_auto

    # 그래프 시각화 (이상치만)📌
    try:
        plot_anomaly_score_distribution(df_full, threshold=-0.20, score_col='Anomaly_Score')
        plot_anomaly_by_user(df_full[df_full['Anomaly'] == 1], user_col=user_col)
        plot_anomaly_by_hour(df_full[df_full['Anomaly'] == 1], user_col=user_col, time_col=time_col)
    except Exception as e:
        print("그래프 시각화 중 오류:", e)

    # 7. 탐지 개수 집계📌
    count_anomaly = int(df_full['Anomaly'].sum())
    total         = len(df_full)

    # 8. 이상 탐지된 항목만 추출📌
    detected = df_full[df_full['Anomaly'] == 1]
    detected.to_csv("pycaret_detected_anomalies.csv", index=False)

    # 표 미리보기(이상치 100개만)📌
    preview_records = detected.head(100).to_dict(orient="records")
    preview_table_html = detected.head(100).to_html(index=False, classes="table table-sm") if len(detected) > 0 else "<p>이상치가 없습니다.</p>"

    # 전체/이상치 records (다운로드용)📌
    all_records = df_full.to_dict(orient="records")
    anomaly_records = detected.to_dict(orient="records")

    # Description HTML 생성📌
    text_html = generate_description(detected, user_col=user_col, time_col=time_col)

    # 9. 결과를 HTML 테이블 + 요약 문자열로 반환📌
    result = {
        "summary": f"이상치 {count_anomaly:,}건 / 전체 {total:,}건",
        "anomaly_count": count_anomaly,
        "total": total,
        "table_html": preview_table_html,
        "records": anomaly_records,   # 이상치만
        "all_records": all_records,   # 전체
        "user_col": user_col,
        "time_col": time_col,
        "columns": list(df_full.columns),
        "result_csv_path": "full_data_with_anomaly_info_readable.csv",
        "text_html": text_html,
    }

    # SHAP 값 계산
    shap_values = shap.TreeExplainer(model).shap_values(processed_data)

    # TF-IDF 컬럼 인덱스 구하기
    tfidf_indices = [processed_data.columns.get_loc(col) for col in tfidf_cols if col in processed_data.columns]

    # SHAP 값에서 TF-IDF 제거
    shap_values_non_tfidf = np.delete(shap_values, tfidf_indices, axis=1)
    
    # TF-IDF 제외한 feature 목록
    # non_tfidf_features = [col for col in processed_data.columns if col not in tfidf_cols]
    
    # == ✅ 행 수 맞추기 == #
    # n_samples = shap_values_non_tfidf.shape[0]
    processed_data_no_tfidf = processed_data[non_tfidf_features]
    print("shap_values_non_tfidf.shape:", shap_values_non_tfidf.shape)
    print("processed_data_no_tfidf.shape:", processed_data_no_tfidf.shape)

    min_samples = min(shap_values_non_tfidf.shape[0], processed_data_no_tfidf.shape[0])

    shap.summary_plot(
        shap_values_non_tfidf[:min_samples],
        processed_data_no_tfidf.iloc[:min_samples],
        feature_names=non_tfidf_features
    )

    # SHAP 값 저장
    np.save(file_path.replace(".csv", "_shap_values.npy"), shap_values_non_tfidf)

    # np.save(file_path.replace(".csv", "_shap_values.npy"), shap_values_non_tfidf)


    # shap_values = shap.TreeExplainer(model).shap_values(processed_data)  #data_scaled를 processed_data 수정. 에러날 수 있음.
    # np.save(file_path.replace(".csv", "_shap_values.npy"), shap_values)
    
    return result