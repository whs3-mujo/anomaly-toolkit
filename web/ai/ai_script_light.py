"""
경량화된 이상 탐지 모델 스크립트 (pyod/shap 제거)
"""
from scipy.stats import rankdata
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
import warnings

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
import category_encoders as ce
import joblib
from collections import Counter

try:
    import chardet
except ImportError:
    chardet = None

from ..restore import restore_and_save_readable_anomalies
from ..services.visualization_service import VisualizationService

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
                        return "새벽"
                    elif 6 <= hour < 12:
                        return "오전"
                    elif 12 <= hour < 18:
                        return "오후"
                    else:
                        return "저녁"
                
                # 시간 컬럼을 시간대로 변환
                hour_df = df.copy()
                hour_df['hour'] = pd.to_datetime(hour_df[time_col], errors='coerce').dt.hour
                hour_df = hour_df.dropna(subset=['hour'])
                
                if not hour_df.empty:
                    hour_df['period'] = hour_df['hour'].apply(time_to_period)
                    period_counts = hour_df.groupby('period').size()
                    
                    if not period_counts.empty:
                        most_frequent_period = period_counts.idxmax()
                        most_frequent_count = period_counts.max()
                        percentage = (most_frequent_count / len(hour_df)) * 100
                        
                        # 시간대별 분석을 포함한 설명
                        description = f"""
                        <div style="line-height: 1.8; color: #333;">
                            <p><strong>🔍 이상 행위 탐지 분석 결과</strong></p>
                            <p>• 전체 로그 수: <span style="color: #2196F3; font-weight: bold;">{total:,}개</span></p>
                            <p>• 이상 탐지된 로그: <span style="color: #F44336; font-weight: bold;">{anomaly_count:,}개</span> 
                               ({(anomaly_count/total*100):.1f}%)</p>
                            <p>• 가장 많은 이상 행위 시간대: <span style="color: #FF9800; font-weight: bold;">{most_frequent_period}</span> 
                               ({most_frequent_count}건, {percentage:.1f}%)</p>
                        </div>
                        """
                        return description
            except Exception as e:
                print(f"시간 분석 중 오류: {e}")
        
        # 시간 분석 실패 또는 시간 컬럼이 없는 경우
        description = f"""
        <div style="line-height: 1.8; color: #333;">
            <p><strong>🔍 이상 행위 탐지 분석 결과</strong></p>
            <p>• 전체 로그 수: <span style="color: #2196F3; font-weight: bold;">{total:,}개</span></p>
            <p>• 이상 탐지된 로그: <span style="color: #F44336; font-weight: bold;">{anomaly_count:,}개</span> 
               ({(anomaly_count/total*100):.1f}%)</p>
        </div>
        """
        return description
    
    # 기존 로직 (사용자별 분석)
    user_anomaly_counts = df.groupby(user_col).size()
    top_users = user_anomaly_counts.nlargest(5)
    
    total_anomalies = len(df)
    total_users = df[user_col].nunique()
    
    # 시간 분석 (시간 컬럼이 있는 경우)
    time_analysis = ""
    if time_col and time_col in df.columns:
        try:
            def time_to_period(hour):
                if 0 <= hour < 6:
                    return "새벽"
                elif 6 <= hour < 12:
                    return "오전"
                elif 12 <= hour < 18:
                    return "오후"
                else:
                    return "저녁"
            
            hour_df = df.copy()
            hour_df['hour'] = pd.to_datetime(hour_df[time_col], errors='coerce').dt.hour
            hour_df = hour_df.dropna(subset=['hour'])
            
            if not hour_df.empty:
                hour_df['period'] = hour_df['hour'].apply(time_to_period)
                period_counts = hour_df.groupby('period').size()
                
                if not period_counts.empty:
                    most_frequent_period = period_counts.idxmax()
                    most_frequent_count = period_counts.max()
                    percentage = (most_frequent_count / len(hour_df)) * 100
                    time_analysis = f"<p>• 가장 많은 이상 행위 시간대: <span style='color: #FF9800; font-weight: bold;'>{most_frequent_period}</span> ({most_frequent_count}건, {percentage:.1f}%)</p>"
        except Exception as e:
            print(f"시간 분석 중 오류: {e}")
    
    user_list = ""
    for i, (user, count) in enumerate(top_users.items(), 1):
        percentage = (count / total_anomalies) * 100
        user_list += f"<span style='margin-right: 15px;'>{i}. <strong>{user}</strong> ({count}건, {percentage:.1f}%)</span>"
        if i % 2 == 0:
            user_list += "<br>"
    
    description = f"""
    <div style="line-height: 1.8; color: #333;">
        <p><strong>🔍 이상 행위 탐지 분석 결과</strong></p>
        <p>• 총 <span style="color: #F44336; font-weight: bold;">{total_anomalies:,}건</span>의 이상 행위가 탐지되었습니다.</p>
        <p>• <span style="color: #2196F3; font-weight: bold;">{total_users:,}명</span>의 사용자에게서 이상 행위가 발견되었습니다.</p>
        {time_analysis}
        <p><strong>상위 이상 행위 사용자:</strong></p>
        <p style="margin-left: 20px;">{user_list}</p>
    </div>
    """
    
    return description

def detect_text_columns(df, threshold=0.5):
    """텍스트 컬럼을 자동으로 감지합니다."""
    text_columns = []
    
    for col in df.columns:
        # 숫자형이 아니고, object 타입이며, NaN이 아닌 값들을 확인
        if df[col].dtype == 'object':
            non_null_values = df[col].dropna()
            if len(non_null_values) > 0:
                # 문자열 타입인 값들의 비율을 계산
                string_values = non_null_values.astype(str)
                # 고유값의 개수가 전체의 일정 비율 이상이거나, 평균 길이가 긴 경우 텍스트로 판단
                unique_ratio = len(string_values.unique()) / len(string_values)
                avg_length = string_values.str.len().mean()
                
                if unique_ratio > threshold or avg_length > 10:
                    text_columns.append(col)
    
    return text_columns

def preprocess_log_data_with_text(df, text_columns=None, scale=True, encode_categorical=True, 
                                user_col=None, time_col=None, max_features=100):
    """
    로그 데이터를 전처리합니다 (경량화 버전)
    """
    if df.empty:
        return pd.DataFrame()
    
    # 복사본 생성
    data = df.copy()
    
    # 텍스트 컬럼 자동 감지
    if text_columns is None:
        text_columns = detect_text_columns(data)
    
    processed_parts = []
    
    # 1. 숫자형 컬럼 처리
    numeric_columns = data.select_dtypes(include=[np.number]).columns.tolist()
    if user_col in numeric_columns:
        numeric_columns.remove(user_col)
    if time_col in numeric_columns:
        numeric_columns.remove(time_col)
    
    if numeric_columns:
        numeric_data = data[numeric_columns].copy()
        numeric_data = numeric_data.fillna(numeric_data.median())
        processed_parts.append(numeric_data)
    
    # 2. 카테고리형 컬럼 처리
    categorical_columns = []
    for col in data.columns:
        if (col not in numeric_columns and 
            col not in text_columns and 
            col != user_col and 
            col != time_col):
            categorical_columns.append(col)
    
    if categorical_columns and encode_categorical:
        cat_data = data[categorical_columns].copy()
        cat_data = cat_data.fillna('missing')
        
        # 각 컬럼별로 개별 처리
        for col in categorical_columns:
            unique_count = cat_data[col].nunique()
            
            if unique_count <= 10:  # 낮은 카디널리티
                encoder = ce.OneHotEncoder(cols=[col], handle_unknown='ignore')
                encoded = encoder.fit_transform(cat_data[[col]])
                encoded.columns = [f"{col}_{suffix}" for suffix in encoded.columns]
                processed_parts.append(encoded)
            else:  # 높은 카디널리티
                encoder = ce.TargetEncoder(cols=[col], handle_unknown='ignore')
                # 타겟이 없으므로 더미 타겟 생성
                dummy_target = np.random.randint(0, 2, len(cat_data))
                encoded = encoder.fit_transform(cat_data[[col]], dummy_target)
                encoded.columns = [f"{col}_encoded"]
                processed_parts.append(encoded)
    
    # 3. 텍스트 컬럼 처리 (TF-IDF)
    for col in text_columns:
        if col in data.columns:
            text_data = data[col].fillna('').astype(str)
            
            if len(text_data.unique()) > 1:  # 중복이 있는 경우에만 처리
                try:
                    vectorizer = TfidfVectorizer(
                        max_features=min(max_features, len(text_data)),
                        stop_words=None,
                        lowercase=True,
                        ngram_range=(1, 1)
                    )
                    
                    tfidf_matrix = vectorizer.fit_transform(text_data)
                    tfidf_df = pd.DataFrame(
                        tfidf_matrix.toarray(),
                        columns=[f"{col}_tfidf_{i}" for i in range(tfidf_matrix.shape[1])]
                    )
                    processed_parts.append(tfidf_df)
                except Exception as e:
                    print(f"텍스트 처리 중 오류 ({col}): {e}")
    
    # 4. 결과 결합
    if processed_parts:
        final_data = pd.concat(processed_parts, axis=1)
    else:
        final_data = pd.DataFrame()
    
    # 5. 스케일링
    if scale and final_data.shape[1] > 0:
        scaler = StandardScaler()
        scaled_data = scaler.fit_transform(final_data)
        final_data = pd.DataFrame(scaled_data, columns=final_data.columns)
    
    return final_data

def lightweight_ensemble_anomaly_detection(data, contamination=0.1, n_estimators=100, random_state=42):
    """
    scikit-learn의 IsolationForest만 사용한 경량화된 이상 탐지
    """
    if data.empty or data.shape[1] == 0:
        return np.array([]), np.array([])
    
    # IsolationForest 모델
    model = IsolationForest(
        contamination=contamination,
        n_estimators=n_estimators,
        random_state=random_state,
        n_jobs=-1
    )
    
    # 예측
    predictions = model.fit_predict(data)
    scores = model.decision_function(data)
    
    # 이상치는 -1, 정상은 1로 반환되므로 0/1로 변환
    binary_predictions = (predictions == -1).astype(int)
    
    # 점수를 0-1 범위로 정규화 (높을수록 이상)
    normalized_scores = (scores.max() - scores) / (scores.max() - scores.min() + 1e-8)
    
    return binary_predictions, normalized_scores

def detect_anomalies(df, user_col='user', time_col='time', 
                    text_columns=None, contamination=0.1, 
                    scale=True, encode_categorical=True, max_features=100):
    """
    경량화된 이상 탐지 메인 함수
    """
    if df.empty:
        return df.copy(), {
            'success': False,
            'message': '데이터가 비어있습니다.',
            'total_rows': 0,
            'anomaly_count': 0
        }
    
    try:
        print("데이터 전처리 시작...")
        
        # 데이터 전처리
        processed_data = preprocess_log_data_with_text(
            df, 
            text_columns=text_columns,
            scale=scale,
            encode_categorical=encode_categorical,
            user_col=user_col,
            time_col=time_col,
            max_features=max_features
        )
        
        if processed_data.empty or processed_data.shape[1] == 0:
            return df.copy(), {
                'success': False,
                'message': '전처리 후 데이터가 비어있습니다.',
                'total_rows': len(df),
                'anomaly_count': 0
            }
        
        print(f"전처리 완료: {processed_data.shape}")
        print("이상 탐지 시작...")
        
        # 이상 탐지 수행
        anomaly_predictions, anomaly_scores = lightweight_ensemble_anomaly_detection(
            processed_data, 
            contamination=contamination
        )
        
        # 결과를 원본 데이터에 추가
        result_df = df.copy()
        result_df['Anomaly'] = anomaly_predictions
        result_df['Anomaly_Score'] = anomaly_scores
        
        # 이상치만 필터링
        anomaly_df = result_df[result_df['Anomaly'] == 1].copy()
        anomaly_count = len(anomaly_df)
        
        print(f"이상 탐지 완료: {anomaly_count}개 탐지")
        
        # 점수 순으로 정렬
        anomaly_df = anomaly_df.sort_values('Anomaly_Score', ascending=False)
        
        return anomaly_df, {
            'success': True,
            'message': f'이상 탐지 완료: {anomaly_count}개 발견',
            'total_rows': len(df),
            'anomaly_count': anomaly_count,
            'contamination': contamination
        }
        
    except Exception as e:
        print(f"이상 탐지 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        
        return df.copy(), {
            'success': False,
            'message': f'이상 탐지 중 오류: {str(e)}',
            'total_rows': len(df),
            'anomaly_count': 0
        }

def analyze_with_ai(file_path, user_col='user', time_col=None, contamination=0.1, 
                   text_columns=None, max_features=100):
    """
    경량화된 AI 분석 메인 함수
    """
    try:
        # 파일 읽기
        df = pd.read_csv(file_path)
        
        if df.empty:
            return {
                'success': False,
                'message': '파일이 비어있습니다.',
                'anomaly_count': 0,
                'total_count': 0
            }
        
        print(f"파일 로드 완료: {len(df)}행")
        
        # 이상 탐지 수행
        anomaly_df, detection_info = detect_anomalies(
            df,
            user_col=user_col,
            time_col=time_col,
            text_columns=text_columns,
            contamination=contamination,
            max_features=max_features
        )
        
        if not detection_info['success']:
            return detection_info
        
        # 결과 저장
        base_filename = file_path.replace('.csv', '')
        
        # 전체 데이터에 이상 점수 추가하여 저장
        full_result_df = df.copy()
        if 'Anomaly' in anomaly_df.columns:
            # 이상치 정보를 전체 데이터에 병합
            anomaly_info = anomaly_df[['Anomaly', 'Anomaly_Score']].copy()
            full_result_df = full_result_df.merge(
                anomaly_info, 
                left_index=True, 
                right_index=True, 
                how='left'
            )
            full_result_df['Anomaly'].fillna(0, inplace=True)
            full_result_df['Anomaly_Score'].fillna(0, inplace=True)
        
        # 파일 저장
        full_result_path = f"{base_filename}_full_data_with_anomaly_info.csv"
        full_result_df.to_csv(full_result_path, index=False)
        
        anomaly_result_path = f"{base_filename}_lightweight_detected_anomalies.csv"
        anomaly_df.to_csv(anomaly_result_path, index=False)
        
        # 설명 생성
        description_text = generate_description(
            anomaly_df, 
            user_col, 
            time_col,
            count_anomaly=detection_info['anomaly_count'],
            total_count=detection_info['total_rows']
        )
        
        print(f"분석 완료: {detection_info['anomaly_count']}개 이상치 탐지")
        
        return {
            'success': True,
            'message': '분석이 완료되었습니다.',
            'anomaly_count': detection_info['anomaly_count'],
            'total_count': detection_info['total_rows'],
            'contamination': contamination,
            'text_html': description_text,
            'anomaly_file_path': anomaly_result_path,
            'full_result_path': full_result_path
        }
        
    except Exception as e:
        print(f"AI 분석 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'success': False,
            'message': f'분석 중 오류가 발생했습니다: {str(e)}',
            'anomaly_count': 0,
            'total_count': 0
        }