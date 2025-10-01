"""
Configuration management for the anomaly detection system.

This module handles application configuration, environment variables,
and default settings for the anomaly detection toolkit.
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ModelConfig:
    """Configuration for anomaly detection models."""
    
    # PyOD IForest model parameters
    contamination: float = 0.05
    random_state: int = 42
    n_estimators: int = 100
    
    # Text processing parameters
    tfidf_max_features: int = 100
    min_text_length: int = 20
    
    # Preprocessing parameters
    encoding_method: str = 'count'
    scale_features: bool = True
    
    # Analysis parameters
    max_preview_rows: int = 100
    shap_max_rows: int = 100


@dataclass
class UIConfig:
    """Configuration for UI components."""
    
    # Dashboard settings
    max_filename_display: int = 20
    default_threshold: float = -0.20
    
    # Graph settings
    graph_height: int = 600
    graph_font_size: int = 16
    top_users_display: int = 10
    
    # File upload settings
    max_file_size_mb: int = 100
    allowed_extensions: list = field(default_factory=lambda: ['.csv'])


@dataclass
class SystemConfig:
    """System-wide configuration settings."""
    
    # File processing
    upload_timeout_seconds: int = 600  # 10 minutes
    max_processing_time: int = 600
    
    # Encoding detection
    encoding_detection_sample_size: int = 10000
    default_encoding: str = 'utf-8'
    
    # Logging
    log_level: str = 'INFO'
    enable_debug: bool = False


class ConfigManager:
    """Manages application configuration from environment variables and defaults."""
    
    def __init__(self):
        self.model = ModelConfig()
        self.ui = UIConfig()
        self.system = SystemConfig()
        self._load_from_env()
    
    def _load_from_env(self) -> None:
        """Load configuration from environment variables."""
        
        # Model configuration
        self.model.contamination = float(os.getenv('MODEL_CONTAMINATION', self.model.contamination))
        self.model.random_state = int(os.getenv('MODEL_RANDOM_STATE', self.model.random_state))
        self.model.tfidf_max_features = int(os.getenv('TFIDF_MAX_FEATURES', self.model.tfidf_max_features))
        
        # UI configuration
        self.ui.max_filename_display = int(os.getenv('UI_MAX_FILENAME_DISPLAY', self.ui.max_filename_display))
        self.ui.default_threshold = float(os.getenv('UI_DEFAULT_THRESHOLD', self.ui.default_threshold))
        
        # System configuration
        self.system.upload_timeout_seconds = int(os.getenv('UPLOAD_TIMEOUT', self.system.upload_timeout_seconds))
        self.system.log_level = os.getenv('LOG_LEVEL', self.system.log_level)
        self.system.enable_debug = os.getenv('ENABLE_DEBUG', 'false').lower() == 'true'
    
    def get_model_params(self) -> Dict[str, Any]:
        """Get model parameters as dictionary."""
        return {
            'contamination': self.model.contamination,
            'random_state': self.model.random_state,
            'n_estimators': self.model.n_estimators,
        }
    
    def get_preprocessing_params(self) -> Dict[str, Any]:
        """Get preprocessing parameters as dictionary."""
        return {
            'encode_method': self.model.encoding_method,
            'scale': self.model.scale_features,
            'tfidf_max_features': self.model.tfidf_max_features,
            'min_avg_length': self.model.min_text_length,
        }


# Global configuration instance
config = ConfigManager()