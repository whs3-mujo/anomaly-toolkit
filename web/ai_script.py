"""
Anomaly Detection AI Script

This module provides the main interface for anomaly detection using machine learning.
It has been refactored to use a modular architecture with clear separation of concerns
for better maintainability and extensibility.
"""
from scipy.stats import rankdata
from pyod.models.ecod import ECOD
from pyod.models.hbos import HBOS           
from pyod.models.iforest import IForest    #추가(채윤)

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
import warnings

# Import new modular components
from .services.analysis_service import AnalysisService, detect_anomalies as new_detect_anomalies
from .pipelines.preprocessing import (
    preprocess_log_data_with_text as new_preprocess,
    detect_text_columns as new_detect_text_columns
)
from .core.config import config

# Legacy imports for backward compatibility
from sklearn.preprocessing import StandardScaler
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from pyod.models.iforest import IForest
import category_encoders as ce
import joblib
import shap
from collections import Counter

# Optional imports
try:
    import chardet
except ImportError:
    chardet = None

# Import other modules
from .restore import restore_and_save_readable_anomalies

# Import refactored services
from .services.shap_service import ShapService
from .services.visualization_service import VisualizationService
def generate_description(df, user_col, time_col, count_anomaly=None, total_count=None):
    import pandas as pd
    from collections import Counter

    # 사용자 칼럼이 'all'인 경우 (모든 데이터가 하나의 사용자로 처리)
    if user_col == 'user' and df[user_col].nunique() == 1 and df[user_col].iloc[0] == 'all':
        # 전달받은 전체 통계를 사용, 없으면 기존 방식 사용
        anomaly_count = count_anomaly if count_anomaly is not None else len(df)
        total = total_count if total_count is not None else len(df)
        
        # 시간 컬럼이 있는 경우 시간대별 분석
        if time_col and time_col in df.columns:
            try:
                def time_to_period(hour):
                    if 0 <= hour < 6:
                        return "새벽시간(00-05시)"
                    elif 6 <= hour < 12:
                        return "오전시간(06-11시)"
                    elif 12 <= hour < 18:
                        return "오후시간(12-17시)"
                    else:
                        return "저녁시간(18-23시)"

                df_copy = df.copy()
                df_copy["hour"] = pd.to_datetime(df_copy[time_col]).dt.hour
                df_copy["period"] = df_copy["hour"].apply(time_to_period)
                period_counts = df_copy["period"].value_counts().to_dict()
                
                period_summary = "<br>".join([f"{period}: <b><span style='color:red;'>{count}건</span></b> ({count/anomaly_count:.1%})" 
                                             for period, count in period_counts.items()])
                
                html = f"""
                <div style='background:#e3f2fd; border-left:4px solid #2196f3; padding:1rem; margin-top:2rem;'>
                <h3 style='margin-top:0;'>종합 평가</h3>
                <div>
                    <b>&lt;전체 사용자 이상 로그 분석&gt;</b><br>
                    이상치 <b><span style='color:red;'>{anomaly_count:,}건</span></b> / 전체 <b>{total:,}건</b><br><br>
                    <b>&lt;시간대별 이상 로그 분포&gt;</b><br>
                    {period_summary}
                </div>
                </div>
                """
                return html
            except Exception as e:
                print(f"시간 데이터 처리 중 오류: {e}")
        
        # 시간 분석이 없거나 실패한 경우
        html = f"""
        <div style='background:#e3f2fd; border-left:4px solid #2196f3; padding:1rem; margin-top:2rem;'>
        <h3 style='margin-top:0;'>종합 평가</h3>
        <div>
            <b>&lt;전체 사용자 이상 로그 분석&gt;</b><br>
            이상치 <b><span style='color:red;'>{anomaly_count:,}건</span></b> / 전체 <b>{total:,}건</b>
        </div>
        </div>
        """
        return html

    # 시간 컬럼 존재 여부 확인
    if time_col is None or time_col not in df.columns:
        if time_col is not None:
            print(f"시간 컬럼 '{time_col}'이 데이터에 없습니다. 사용 가능한 컬럼: {df.columns.tolist()}")
        else:
            print("시간 컬럼이 지정되지 않아 시간 분석을 생략합니다.")
        # 시간 분석 없이 사용자별 분석만 수행
        user_counts = Counter(df[user_col]) if user_col in df.columns else {}
        anomaly_count = count_anomaly if count_anomaly is not None else len(df)
        total = total_count if total_count is not None else len(df)
        
        if user_counts:
            top_users = user_counts.most_common(5)
            top_summary = ", ".join([f"{u}: {c}건 ({c/anomaly_count:.1%})" for u, c in top_users])
            top_total = sum([c for _, c in top_users])
            top_ratio = f"{top_total}건({top_total/anomaly_count:.1%})"
            
            items = [item.strip() for item in top_summary.split(',') if item.strip()]
            formatted_top_summary = "<br>".join([
                f"{user}: <b><span style='color:red;'>{count}</span></b>"
                for user, count in (item.split(': ', 1) for item in items)
            ])
            
            html = f"""
            <div style='background:#e3f2fd; border-left:4px solid #2196f3; padding:1rem; margin-top:2rem;'>
            <h3 style='margin-top:0;'>종합 평가</h3>
            <div>
                <b>&lt;전체 데이터 분석&gt;</b><br>
                이상치 <b><span style='color:red;'>{anomaly_count:,}건</span></b> / 전체 <b>{total:,}건</b><br><br>
                <b>&lt;상위 사용자 이상 로그 개수&gt;</b><br>
                {formatted_top_summary}<br>
                ➤ 상위 5명의 사용자가 전체 이상 로그 <b><span style='color:red;'>{anomaly_count:,}건</span></b> 중 <b style='color:red;'>{top_ratio}</b>을 차지합니다.
            </div>
            </div>
            """
            return html
        else:
            return "<div>분석할 수 있는 데이터가 부족합니다.</div>"

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
    try:
        df["hour"] = pd.to_datetime(df[time_col]).dt.hour
        df["period"] = df["hour"].apply(time_to_period)
        period_counts = df["period"].value_counts().to_dict()
    except Exception as e:
        print(f"시간 데이터 처리 중 오류: {e}")
        # 시간 분석 실패 시 사용자별 분석만 수행
        user_counts = Counter(df[user_col]) if user_col in df.columns else {}
        anomaly_count = count_anomaly if count_anomaly is not None else len(df)
        total = total_count if total_count is not None else len(df)
        
        if user_counts:
            top_users = user_counts.most_common(5)
            top_summary = ", ".join([f"{u}: {c}건 ({c/anomaly_count:.1%})" for u, c in top_users])
            top_total = sum([c for _, c in top_users])
            top_ratio = f"{top_total}건({top_total/anomaly_count:.1%})"
            
            items = [item.strip() for item in top_summary.split(',') if item.strip()]
            formatted_top_summary = "<br>".join([
                f"{user}: <b><span style='color:red;'>{count}</span></b>"
                for user, count in (item.split(': ', 1) for item in items)
            ])
            
            html = f"""
            <div style='background:#e3f2fd; border-left:4px solid #2196f3; padding:1rem; margin-top:2rem;'>
            <h3 style='margin-top:0;'>종합 평가</h3>
            <div>
                <b>&lt;전체 데이터 분석&gt;</b><br>
                이상치 <b><span style='color:red;'>{anomaly_count:,}건</span></b> / 전체 <b>{total:,}건</b><br><br>
                <b>&lt;상위 사용자 이상 로그 개수&gt;</b><br>
                {formatted_top_summary}<br>
                ➤ 상위 5명의 사용자가 전체 이상 로그 <b><span style='color:red;'>{anomaly_count:,}건</span></b> 중 <b style='color:red;'>{top_ratio}</b>을 차지합니다.
            </div>
            </div>
            """
            return html
        else:
            return "<div>분석할 수 있는 데이터가 부족합니다.</div>"

    # 2. 사용자별 이상 로그 수
    user_counts = Counter(df[user_col])
    anomaly_count = count_anomaly if count_anomaly is not None else len(df)
    total = total_count if total_count is not None else len(df)

    top_users = user_counts.most_common(5)
    top_summary = ", ".join([f"{u}: {c}건 ({c/anomaly_count:.1%})" for u, c in top_users])
    top_total = sum([c for _, c in top_users])
    top_ratio = f"{top_total}건({top_total/anomaly_count:.1%})"

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
        <b>&lt;전체 데이터 분석&gt;</b><br>
        이상치 <b><span style='color:red;'>{anomaly_count:,}건</span></b> / 전체 <b>{total:,}건</b><br><br>
        <b>&lt;시간대별 이상 로그 분포&gt;</b><br>
        {"<br>".join([
            f"{k}: <b><span style='color:red;'>{v}건</span></b> ({v/anomaly_count:.1%})"
            for k, v in sorted(period_counts.items())
        ])}<br>
        ➤ <b><span style='color:red;'>{max(period_counts, key=period_counts.get)}</b>에 가장 많은 이상 로그가 집중되어 있습니다.
    </div>
    <div>
        <b>&lt;상위 사용자 이상 로그 개수&gt;</b><br>
        {formatted_top_summary}<br>
        ➤ 상위 5명의 사용자가 전체 이상 로그 <b><span style='color:red;'>{anomaly_count:,}건</span></b> 중 <b style='color:red;'>{top_ratio}</b>을 차지합니다.
    </div>
    </div>
    """
    return html



# 텍스트 컬럼 탐지
def detect_text_columns(df, min_avg_length=20):
    candidate_cols = df.select_dtypes(include=['object', 'string']).columns
    return [col for col in candidate_cols if df[col].astype(str).apply(len).mean() >= min_avg_length]

# 전처리
def preprocess_log_data_with_text(df, encode_method='count', scale=True, tfidf_max_features=100):
    encoder = None
    
    # 빈 값이 많은 컬럼도 유지하되, 적절히 처리
    df = df.copy()

    # 숫자형 컬럼의 빈 값을 0으로 채우기
    numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns.tolist()
    for col in numeric_cols:
        df[col] = df[col].fillna(0)

    # 텍스트/범주형 분리
    text_cols = detect_text_columns(df)
    categorical_cols = df.select_dtypes(include=['object', 'category', 'bool']).columns
    categorical_cols = [col for col in categorical_cols if col not in text_cols]

    # 범주형 컬럼의 빈 값을 "Unknown"으로 채우기
    for col in categorical_cols:
        df[col] = df[col].fillna("Unknown")

    # 범주형 인코딩
    if categorical_cols:
        if encode_method == 'count':
            encoder = ce.CountEncoder()
            encoded = encoder.fit_transform(df[categorical_cols])
        else:
            raise ValueError("지원되지 않는 인코딩 방식입니다.")
    else:
        encoded = pd.DataFrame(index=df.index)

    # 텍스트 TF-IDF
    tfidf_df_list = []
    for col in text_cols:
        try:
            tfidf_vectorizer = TfidfVectorizer(max_features=min(tfidf_max_features, len(df)//2))
            tfidf_matrix = tfidf_vectorizer.fit_transform(df[col].astype(str).fillna(''))
            # 칼럼명에 원본 칼럼명을 명확히 포함
            column_prefix = col.replace(' ', '_').lower()
            tfidf_df = pd.DataFrame(
                tfidf_matrix.toarray(),
                columns=[f"{column_prefix}_tfidf_{i}" for i in range(tfidf_matrix.shape[1])]
            )
            tfidf_df_list.append(tfidf_df)
        except Exception as e:
            print(f"TF-IDF 처리 중 오류 (컬럼 {col}): {e}")
            continue
    tfidf_combined = pd.concat(tfidf_df_list, axis=1) if tfidf_df_list else pd.DataFrame(index=df.index)

    # 숫자형, 인코딩된 범주형, TF-IDF 특성 결합
    df_numeric = df[numeric_cols].reset_index(drop=True)
    df_encoded = encoded.reset_index(drop=True)
    tfidf_combined = tfidf_combined.reset_index(drop=True)
    final_data = pd.concat([df_numeric, df_encoded, tfidf_combined], axis=1)  # , tfidf_combined

    # 스케일링
    if scale and final_data.shape[1] > 0:
        scaler = StandardScaler()
        final_data = pd.DataFrame(scaler.fit_transform(final_data), columns=final_data.columns)

    return final_data, categorical_cols, encoder


# 앙상블 (ECOD + COPOD + HBOS [+IForest])
def cdf_normalize(x):
    """스코어를 랭크→[0,1]로 정규화(CDF 근사)"""
    x = np.asarray(x).ravel()
    ranks = rankdata(x, method='average')
    return (ranks - 1) / (len(ranks) - 1 + 1e-12)


def fit_predict_ensemble_fast(
    X,
    mode="recall",         # 'recall' | 'balanced' | 'weighted'
    q=0.05,                # 상위 q 비율을 이상치로 라벨링
    hbos_n_bins=30,        # HBOS 파라미터
    include_iforest=True,  # ← IForest 포함 여부
    if_n_estimators=200,
    if_max_samples=256,
    if_random_state=42,
    weights=None,          # mode='weighted'일 때 dict 예: {'ecod':0.3,'copod':0.3,'hbos':0.2,'iforest':0.2}
):
    """
    ECOD + COPOD + HBOS (+ IForest) 앙상블
    - 'recall'   : max/soft-OR (재현율 극대화)
    - 'balanced' : CDF 평균 (균형형)
    - 'weighted' : CDF 가중 평균 (정밀도/안정성 미세조정)
    """
    # --- 재현성(난수 의존 모델 없음) ---
    old_state = np.random.get_state()
    np.random.seed(if_random_state)

    try:
        models = [
            ("ecod",  ECOD()),
            ("hbos",  HBOS(n_bins=hbos_n_bins)),  # HBOS 추가
        ]
        if include_iforest:
            ms = min(if_max_samples, X.shape[0]) if isinstance(if_max_samples, int) else if_max_samples
            # feature_names 경고 해결을 위해 numpy array로 변환
            X_array = X.values if hasattr(X, 'values') else X
            models.append(("iforest", IForest(n_estimators=if_n_estimators,
                                              max_samples=ms,
                                              random_state=if_random_state)))

        scores_norm = []
        raw_scores = {}
        names = []
        for name, clf in models:
            # IsolationForest feature_names 경고 해결
            if name == "iforest":
                X_input = X.values if hasattr(X, 'values') else X
            else:
                X_input = X
            
            clf.fit(X_input)
            s = clf.decision_function(X_input)   # 클수록 이상치
            raw_scores[name] = s
            scores_norm.append(cdf_normalize(s))
            names.append(name)

        S = np.vstack(scores_norm)  # (n_models, n_samples)

        if mode == "recall":
            ens = S.max(axis=0)  # soft-OR
        elif mode == "balanced":
            ens = S.mean(axis=0)
        elif mode == "weighted":
            if not weights:
                weights = {n: 1.0 for n in names}
            w = np.array([float(weights.get(n, 0.0)) for n in names])
            if w.sum() <= 0:
                w = np.ones_like(w)
            w = w / w.sum()
            ens = (w.reshape(-1, 1) * S).sum(axis=0)
        elif mode == "median":                           
            ens = np.median(S, axis=0)                 
        else:
            raise ValueError("mode must be one of {'recall','balanced','weighted'}")

        thr = np.quantile(ens, 1 - q)
        y_pred = (ens >= thr).astype(int)  # 1: 이상치
        return y_pred, ens, raw_scores, models

    finally:
        np.random.set_state(old_state)


# 메인 파이프라인
def detect_anomalies(
    file_path,
    exclude_columns=None,
    user_col=None,
    time_col=None,
    mode="recall",
    q=0.05,
    include_iforest=True,
    if_n_estimators=200,
    if_max_samples=256,
    if_random_state=42,
    hbos_n_bins=30,
):
    """
    업로드된 CSV 파일 경로(file_path)와 제외할 칼럼 리스트(exclude_columns)를 받아
    1) 전처리 → 2) ECOD+HBOS+IForest 앙상블 -> 3) HTML 테이블 형태 결과 반환
    mode: 'recall' | 'balanced' | 'weighted'
    q   : 상위 q 비율 컷(기존 contamination 역할)
    """

    # 인코딩 자동 감지
    if chardet:
        with open(file_path, 'rb') as f:
            raw_data = f.read(10000)
            result = chardet.detect(raw_data)
            detected_encoding = result['encoding'] if result['encoding'] else 'utf-8'
    else:
        detected_encoding = 'utf-8'

    # 1. 데이터 불러오기 (원본 유지)
    data = pd.read_csv(file_path, encoding=detected_encoding)

    # 사용자 칼럼 기본 설정
    if user_col is None or user_col == "":
        data['user'] = 'all'
        user_col = 'user'

    if time_col is None or time_col == "":
        time_col = None

    # 제외할 칼럼 제거
    if exclude_columns:
        data = data.drop(columns=[col for col in exclude_columns if col in data.columns])

    # user_col 은 탐지에서 제거
    data_for_model = data.copy()
    if user_col is not None and user_col in data_for_model.columns:
        data_for_model.drop(columns=[user_col], inplace=True)

    # 2. 전처리
    processed_data, categorical_cols, encoder = preprocess_log_data_with_text(
        data_for_model,
        encode_method='count',
        scale=True,
        tfidf_max_features=100
    )

    if processed_data.shape[1] == 0:
            raise ValueError("전처리 결과 특성이 없습니다. (모든 열이 제거되었을 수 있음)")

    # 3. 이상치 탐지
    y_pred, ens_score, indiv_scores, models = fit_predict_ensemble_fast(
        processed_data,
        mode=mode, q=q,
        include_iforest=include_iforest,
        if_n_estimators=if_n_estimators,
        if_max_samples=if_max_samples,
        if_random_state=if_random_state,
        hbos_n_bins=hbos_n_bins
    )
    
  # 4. 결과 합치기
    results = processed_data.copy().reset_index(drop=True)
    results['Anomaly'] = y_pred
    results['Anomaly_Score'] = ens_score
    
    # Anomaly_Score 기준 내림차순 정렬
    sorted_results = results.sort_values(by='Anomaly_Score', ascending=False).reset_index(drop=True)

    # SHAP 입력값으로 사용할 DataFrame 생성
    forshap_input = sorted_results.drop(columns=['Anomaly', 'Anomaly_Score'], errors='ignore')
    forshap_input = forshap_input.round(6)
    forshap_input = forshap_input.head(100)

    # user_col, time_col 복원
    if user_col and user_col in data.columns and user_col not in results.columns:
        results[user_col] = data[user_col].reset_index(drop=True)

    if time_col and time_col in data.columns and time_col not in results.columns:
        results[time_col] = data[time_col].reset_index(drop=True)

    # 5. 결과 출력
    count_anomaly = results['Anomaly'].sum()
    total = len(results)
    print(f"\n 이상치로 판단한 로그 개수: {count_anomaly:,}건 / 전체 {total:,}건")

    # 원본 정보에서 인코딩된 컬럼들을 제거하고 합치기 
    encoded_columns = [col for col in categorical_cols if col in results.columns]  
    results_cleaned = results.drop(columns=encoded_columns, errors='ignore') 

    # 파일명 생성을 먼저 수행
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = file_path.replace('.csv', '') + f"_{timestamp}"

    # 5. SHAP 그래프를 그리기 위한 파일 생성(1) - 서비스로 분리
    ShapService.save_model_and_data(models, forshap_input, base_filename)

    # 이상치 점수 컬럼명 통일
    if 'Anomaly_Score' not in results.columns and 'Anomaly_Score' in results.columns:
        results['Anomaly_Score'] = results['Anomaly_Score']
    elif 'Anomaly_Score' not in results.columns and 'Anomaly Score' in results.columns:
        results['Anomaly_Score'] = results['Anomaly Score']
    elif 'Anomaly_Score' not in results.columns and 'anomaly_score' in results.columns:
        results['Anomaly_Score'] = results['anomaly_score']

    # 복원한 문자열 컬럼을 결과에 다시 붙이기 (중복 컬럼 방지)
    results_with_info = pd.concat([results_cleaned, data.reset_index(drop=True)], axis=1)

    # 6. 결과 저장
    # results_with_info = pd.concat([results_cleaned.drop(columns=tfidf_cols, errors='ignore'), original_info], axis=1)
    # results_with_info = pd.concat([results, original_info], axis=1)
    full_anomaly_path = f"{base_filename}_full_data_with_anomaly_info.csv"
    results_with_info.to_csv(full_anomaly_path, index=False)

    if encoder is not None:
        readable_anomaly_path = f"{base_filename}_full_data_with_anomaly_info_readable.csv"
        restore_and_save_readable_anomalies(
        anomaly_csv_path=full_anomaly_path,
        encoder_mapping_dict=encoder.mapping,
        output_path=readable_anomaly_path
    )
        output_path = readable_anomaly_path
    else:
        print("Encoder가 없어서 복원 단계 스킵")
        output_path = full_anomaly_path

    # 복원된 전체 데이터 로드 
    df_full = pd.read_csv(output_path)

    # 복원된 컬럼만 남기고, .1 붙은 컬럼명을 원래대로 변경 
    for col in df_full.columns:
        if col.endswith('.1'):
            orig_col = col[:-2]
            if orig_col in df_full.columns:
                df_full.drop(columns=[orig_col], inplace=True)
            df_full.rename(columns={col: orig_col}, inplace=True)

    # 그래프 시각화 - 서비스로 분리
    graphs = VisualizationService.generate_all_graphs(
        df_full=df_full, 
        user_col=user_col, 
        time_col=time_col, 
        score_col='Anomaly_Score', 
        threshold=-0.20
    )
    score_distribution_html = graphs['score_distribution_html']
    user_graph_html = graphs['user_graph_html']
    hour_graph_html = graphs['hour_graph_html']

    # 7. 탐지 개수 집계 - 그래프와 동일한 df_full 사용
    count_anomaly = int(df_full['Anomaly'].sum())  # df_full에서 이상치 개수
    total = len(df_full)  # df_full의 전체 개수

    # 8. 이상 탐지된 항목만 추출 - 그래프와 동일한 데이터 사용
    df_anomaly_only = df_full[df_full['Anomaly'] == 1]  # 그래프와 동일한 변수명 사용
    detected_anomalies_path = f"{base_filename}_pyod_detected_anomalies.csv"
    df_anomaly_only.to_csv(detected_anomalies_path, index=False)

    # TF-IDF 컬럼은 제외하고 표를 생성
    tfidf_cols = [col for col in df_anomaly_only.columns if '_tfidf_' in col]
    detected_for_table = df_anomaly_only.drop(columns=tfidf_cols)

    # Anomaly_Score 기준 내림차순 정렬 후 상위 100개 추출
    preview_top100 = detected_for_table.sort_values(by="Anomaly_Score", ascending=False).head(100)

    # 표 미리보기(상위 100개만)
    preview_records = preview_top100.to_dict(orient="records")
    preview_table_html = preview_top100.to_html(index=False, classes="table table-sm") if len(preview_top100) > 0 else "<p>이상치가 없습니다.</p>"

    # JSON 호환 가능하도록 데이터 정리하는 함수
    def clean_for_json(obj):
        """numpy 타입과 NaN 값을 JSON 호환 타입으로 변환"""
        if isinstance(obj, dict):
            return {k: clean_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [clean_for_json(v) for v in obj]
        elif pd.isna(obj):
            return None
        elif isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return obj

    # 전체/이상치 records (다운로드용)
    # 대시보드 표시용: 상위 100개만
    anomaly_records_preview = clean_for_json(detected_for_table.head(100).to_dict(orient="records"))
    all_records_preview = clean_for_json(df_full.drop(columns=tfidf_cols).head(100).to_dict(orient="records"))
    
    # 다운로드용: 전체 데이터
    anomaly_records = clean_for_json(detected_for_table.to_dict(orient="records"))
    all_records = clean_for_json(df_full.drop(columns=tfidf_cols).to_dict(orient="records"))

    # Description HTML 생성 - 그래프와 동일한 데이터 사용 (df_anomaly_only는 위에서 이미 정의됨)
    text_html = generate_description(df_anomaly_only, user_col=user_col, time_col=time_col, 
                                    count_anomaly=count_anomaly, total_count=total)

    # 9. 결과를 HTML 테이블 + 요약 문자열로 반환
    result = {
        "summary": f"이상치 {count_anomaly:,}건 / 전체 {total:,}건",
        "anomaly_count": int(count_anomaly),  # numpy int를 Python int로 변환
        "total": int(total),  # numpy int를 Python int로 변환
        "q": float(q),  # q(이상치 비율) 값 추가
        "table_html": preview_table_html,  # TF-IDF 컬럼이 빠진 표(대시보드용)
        "records": anomaly_records,   # 이상치 결과 전체 (다운로드용)
        "records_preview": anomaly_records_preview,  # 이상치 결과 상위 100개 (표시용)
        "all_records": all_records,   # 전체 결과 전체 (다운로드용)
        "all_records_preview": all_records_preview,  # 전체 결과 상위 100개 (표시용)
        "user_col": user_col,
        "time_col": time_col,
        "columns": [str(col) for col in df_full.columns],  # 컬럼명도 문자열로 변환
        "result_csv_path": output_path,  # 동적 경로 사용
        "text_html": text_html,
        # 그래프 HTML 추가
        "score_distribution_html": score_distribution_html,
        "user_graph_html": user_graph_html, 
        "hour_graph_html": hour_graph_html,
    }

    # 10. SHAP 그래프를 그리기 위한 파일 생성(2)
    ShapService.calculate_and_save_shap_values(models, forshap_input, base_filename)

    return result


