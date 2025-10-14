"""
AI 모델 및 전처리 파이프라인을 위한 하이퍼파라미터 설정.

"""

def get_ai_config():
    """AI 관련 하이퍼파라미터를 반환합니다."""
    
    config = {
        "model_params": {
            # PyOD IForest 모델 파라미터
            "contamination": 0.05,
            "random_state": 42,
            "n_estimators": 100,
        },
        "preprocessing_params": {
            # 텍스트 처리 파라미터
            "tfidf_max_features": 100,
            "min_text_length": 20,
            
            # 인코딩 및 스케일링 파라미터
            "encoding_method": 'count',
            "scale_features": True,
        },
        "analysis_params": {
            # SHAP 분석에 사용할 최대 행 수
            "shap_max_rows": 100,
            # 프론트엔드 미리보기에 표시할 최대 행 수
            "max_preview_rows": 100,
        }
    }
    
    return config
