"""
이상 탐지 시스템을 위한 설정 관리.

이 모듈은 이상 탐지 툴킷의 애플리케이션 설정, 환경 변수,
기본값 등을 처리합니다.
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ModelConfig:
    """이상 탐지 모델을 위한 설정입니다."""
    
    # PyOD IForest 모델 파라미터
    contamination: float = 0.05
    random_state: int = 42
    n_estimators: int = 100
    
    # 텍스트 처리 파라미터
    tfidf_max_features: int = 100
    min_text_length: int = 20
    
    # 전처리 파라미터
    encoding_method: str = 'count'
    scale_features: bool = True
    
    # 분석 파라미터
    max_preview_rows: int = 100
    shap_max_rows: int = 100


@dataclass
class UIConfig:
    """UI 컴포넌트를 위한 설정입니다."""
    
    # 대시보드 설정
    max_filename_display: int = 20
    default_threshold: float = -0.20
    
    # 그래프 설정
    graph_height: int = 600
    graph_font_size: int = 16
    top_users_display: int = 10
    
    # 파일 업로드 설정
    max_file_size_mb: int = 100
    allowed_extensions: list = field(default_factory=lambda: ['.csv'])


@dataclass
class SystemConfig:
    """시스템 전반의 설정입니다."""
    
    # 파일 처리
    upload_timeout_seconds: int = 600  # 10분
    max_processing_time: int = 600
    
    # 인코딩 탐지
    encoding_detection_sample_size: int = 10000
    default_encoding: str = 'utf-8'
    
    # 로깅
    log_level: str = 'INFO'
    enable_debug: bool = False


class ConfigManager:
    """환경 변수와 기본값으로부터 애플리케이션 설정을 관리합니다."""
    
    def __init__(self):
        self.model = ModelConfig()
        self.ui = UIConfig()
        self.system = SystemConfig()
        self._load_from_env()
    
    def _load_from_env(self) -> None:
        """환경 변수로부터 설정을 로드합니다."""
        
        # 모델 설정
        self.model.contamination = float(os.getenv('MODEL_CONTAMINATION', self.model.contamination))
        self.model.random_state = int(os.getenv('MODEL_RANDOM_STATE', self.model.random_state))
        self.model.tfidf_max_features = int(os.getenv('TFIDF_MAX_FEATURES', self.model.tfidf_max_features))
        
        # UI 설정
        self.ui.max_filename_display = int(os.getenv('UI_MAX_FILENAME_DISPLAY', self.ui.max_filename_display))
        self.ui.default_threshold = float(os.getenv('UI_DEFAULT_THRESHOLD', self.ui.default_threshold))
        
        # 시스템 설정
        self.system.upload_timeout_seconds = int(os.getenv('UPLOAD_TIMEOUT', self.system.upload_timeout_seconds))
        self.system.log_level = os.getenv('LOG_LEVEL', self.system.log_level)
        self.system.enable_debug = os.getenv('ENABLE_DEBUG', 'false').lower() == 'true'
    
    def get_model_params(self) -> Dict[str, Any]:
        """모델 파라미터를 딕셔너리로 반환합니다."""
        return {
            'contamination': self.model.contamination,
            'random_state': self.model.random_state,
            'n_estimators': self.model.n_estimators,
        }
    
    def get_preprocessing_params(self) -> Dict[str, Any]:
        """전처리 파라미터를 딕셔너리로 반환합니다."""
        return {
            'encode_method': self.model.encoding_method,
            'scale': self.model.scale_features,
            'tfidf_max_features': self.model.tfidf_max_features,
            'min_avg_length': self.model.min_text_length,
        }


# 전역 설정 인스턴스
config = ConfigManager()