# ai_script.py

import pandas as pd
from sklearn.preprocessing import StandardScaler
from pycaret.anomaly import setup, create_model, assign_model
import category_encoders as ce
from .restore import restore_and_save_readable_anomalies
from .visualize_graph import (
    detect_user_and_time_columns,
    plot_anomaly_by_hour,
    plot_anomaly_by_user,
    plot_anomaly_score_distribution
)

def detect_anomalies(file_path, exclude_columns=None, user_col=None, time_col=None):
    """
    업로드된 CSV 파일 경로(file_path)와 제외할 칼럼 리스트(exclude_columns)를 받아
    1) 전처리 → 2) PyCaret 이상 탐지 → 3) HTML 테이블 형태 결과 반환
    """
    # 1. 데이터 불러오기
    data = pd.read_csv(file_path, index_col=0).dropna()

    # 제외할 칼럼이 있으면 제거
    if exclude_columns:
        data = data.drop(columns=[col for col in exclude_columns if col in data.columns])

    # 2. 숫자형 / 문자형 분리
    numeric_cols     = data.select_dtypes(include=['int64', 'float64']).columns
    categorical_cols = data.select_dtypes(include=['object']).columns

    # 복원용 원본 정보 백업 (예: user_id, timestamp 등)
    original_info = data[categorical_cols].reset_index(drop=True)

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

    # 이상치 점수 컬럼명 통일
    if 'Anomaly_Score' not in results.columns and 'Anomaly_Score' in results.columns:
        results['Anomaly_Score'] = results['Anomaly_Score']
    elif 'Anomaly_Score' not in results.columns and 'Anomaly Score' in results.columns:
        results['Anomaly_Score'] = results['Anomaly Score']
    elif 'Anomaly_Score' not in results.columns and 'anomaly_score' in results.columns:
        results['Anomaly_Score'] = results['anomaly_score']

    # 복원한 문자열 컬럼을 결과에 다시 붙이기
    results_with_info = pd.concat([results, original_info], axis=1)

    # 전체 결과 저장
    results_with_info.to_csv("full_data_with_anomaly_info.csv", index=False)

    # 전체 결과 복원 (문자열 컬럼)
    restore_and_save_readable_anomalies(
        anomaly_csv_path="full_data_with_anomaly_info.csv",
        encoder_mapping_dict=encoder.mapping,
        output_path="full_data_with_anomaly_info_readable.csv"
    )

    # 6. 탐지 개수 집계
    count_anomaly = int(results['Anomaly'].sum())
    total         = len(results)

    # 7. 이상 탐지된 항목만 추출
    detected = results_with_info[results_with_info['Anomaly'] == 1]
    detected.to_csv("pycaret_detected_anomalies.csv", index=False)

    # 복원된 전체 데이터 로드
    df_full = pd.read_csv("full_data_with_anomaly_info_readable.csv")

    # 사용자/시간 컬럼 자동 감지 (없으면 직접 입력)
    if not user_col or not time_col:
        user_col_auto, time_col_auto = detect_user_and_time_columns(df_full)
        user_col = user_col or user_col_auto
        time_col = time_col or time_col_auto

    # 그래프 시각화 (이상치만)
    try:
        plot_anomaly_score_distribution(df_full, threshold=-0.20, score_col='Anomaly_Score')
        plot_anomaly_by_user(df_full[df_full['Anomaly'] == 1], user_col=user_col)
        plot_anomaly_by_hour(df_full[df_full['Anomaly'] == 1], user_col=user_col, time_col=time_col)
    except Exception as e:
        print("그래프 시각화 중 오류:", e)

    # 표 미리보기(이상치 100개만)
    preview_records = detected.head(100).to_dict(orient="records")
    preview_table_html = detected.head(100).to_html(index=False, classes="table table-sm") if len(detected) > 0 else "<p>이상치가 없습니다.</p>"

    # 전체/이상치 records (다운로드용)
    all_records = results_with_info.to_dict(orient="records")
    anomaly_records = detected.to_dict(orient="records")

    # 8. 결과를 HTML 테이블 + 요약 문자열로 반환
    result = {
        "summary": f"이상치 {int(detected['Anomaly'].sum()):,}건 / 전체 {len(results_with_info):,}건",
        "anomaly_count": int(detected['Anomaly'].sum()),
        "total": int(len(results_with_info)),
        "table_html": preview_table_html,
        "records": anomaly_records,   # 이상치만
        "all_records": all_records,   # 전체
        "user_col": user_col,
        "time_col": time_col,
        "columns": list(results_with_info.columns),
    }
    return result
