"""
PyOD 모델을 사용한 이상 탐지 파이프라인.

이 모듈은 일관된 입출력 인터페이스를 통해 다양한 PyOD 모델을 사용하여
이상 탐지를 위한 모듈식 인터페이스를 제공합니다.
"""

import pandas as pd
import numpy as np
from typing import Tuple, Dict, Any, Optional
import joblib
from pyod.models.iforest import IForest

from ..core.exceptions import ModelTrainingError
# AI 관련 설정을 중앙에서 관리하기 위해 ai_config.py를 임포트합니다.
from .ai_config import get_ai_config


class AnomalyDetector:
    """PyOD 모델을 사용한 모듈식 이상 탐지기."""
    
    def __init__(self, model_name: str = 'iforest', model_params: Dict[str, Any] = None):
        """
        이상 탐지기를 초기화합니다.
        
        Args:
            model_name: 사용할 모델의 이름
            model_params: 모델별 파라미터. 지정하지 않으면 ai_config.py에서 로드됩니다.
        """
        self.model_name = model_name
        
        # model_params가 제공되지 않으면 ai_config.py에서 로드합니다.
        if model_params is None:
            ai_config = get_ai_config()
            self.model_params = ai_config.get("model_params", {})
        else:
            self.model_params = model_params
            
        self.model = None
        self.is_fitted = False
    
    def _create_model(self):
        """model_name에 따라 이상 탐지 모델을 생성합니다."""
        if self.model_name == 'iforest':
            # ai_config.py에서 로드된 파라미터를 사용합니다.
            self.model = IForest(
                contamination=self.model_params.get('contamination', 0.05),
                random_state=self.model_params.get('random_state', 42),
                n_estimators=self.model_params.get('n_estimators', 100)
            )
        else:
            raise ValueError(f"지원되지 않는 모델입니다: {self.model_name}")
    
    def fit(self, X: pd.DataFrame) -> 'AnomalyDetector':
        """
        이상 탐지 모델을 학습시킵니다.
        
        Args:
            X: 학습 데이터
            
        Returns:
            메서드 체인을 위한 Self
            
        Raises:
            ModelTrainingError: 모델 학습 실패 시
        """
        try:
            if self.model is None:
                self._create_model()
            
            # numpy 배열로 변환 (필요한 경우)
            if isinstance(X, pd.DataFrame):
                X_array = X.values
            else:
                X_array = X
            
            self.model.fit(X_array)
            self.is_fitted = True
            
            return self
            
        except Exception as e:
            raise ModelTrainingError(f"모델 학습 실패: {str(e)}")
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        이상 예측을 수행합니다.
        
        Args:
            X: 입력 데이터
            
        Returns:
            이진 예측 결과 (1: 이상, 0: 정상)
            
        Raises:
            ModelTrainingError: 모델이 학습되지 않은 경우
        """
        if not self.is_fitted:
            raise ModelTrainingError("예측 전에 모델을 학습시켜야 합니다")
        
        # numpy 배열로 변환 (필요한 경우)
        if isinstance(X, pd.DataFrame):
            X_array = X.values
        else:
            X_array = X
        
        return self.model.predict(X_array)
    
    def decision_function(self, X: pd.DataFrame) -> np.ndarray:
        """
        이상 점수 계산합니다.
        
        Args:
            X: 입력 데이터
            
        Returns:
            이상 점수
            
        Raises:
            ModelTrainingError: 모델이 학습되지 않은 경우
        """
        if not self.is_fitted:
            raise ModelTrainingError("점수 계산 전에 모델을 학습시켜야 합니다")
        
        # numpy 배열로 변환 (필요한 경우)
        if isinstance(X, pd.DataFrame):
            X_array = X.values
        else:
            X_array = X
        
        return self.model.decision_function(X_array)
    
    def fit_predict(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        모델을 학습하고 한 번에 이상을 예측합니다.
        
        Args:
            X: 입력 데이터
            
        Returns:
            (예측 결과, 점수) 튜플
        """
        self.fit(X)
        predictions = self.predict(X)
        scores = self.decision_function(X)
        
        return predictions, scores
    
    def save_model(self, filepath: str) -> None:
        """
        학습된 모델을 파일에 저장합니다.
        
        Args:
            filepath: 모델을 저장할 경로
        """
        if not self.is_fitted:
            raise ModelTrainingError("학습되지 않은 모델은 저장할 수 없습니다")
        
        joblib.dump(self.model, filepath)
    
    def load_model(self, filepath: str) -> 'AnomalyDetector':
        """
        파일에서 학습된 모델을 로드합니다.
        
        Args:
            filepath: 모델을 로드할 경로
            
        Returns:
            메서드 체인을 위한 Self
        """
        self.model = joblib.load(filepath)
        self.is_fitted = True
        return self
    
    def get_feature_importance(self, X: pd.DataFrame, method: str = 'shap') -> Optional[np.ndarray]:
        """
        특성 중요도 점수를 얻습니다.
        
        Args:
            X: 입력 데이터
            method: 중요도 계산 방법 ('shap' 지원)
            
        Returns:
            특성 중요도 점수 또는 사용 불가능한 경우 None
        """
        if not self.is_fitted:
            raise ModelTrainingError("특성 중요도를 얻기 전에 모델을 학습시켜야 합니다.")
        
        if method == 'shap':
            try:
                import shap
                
                ai_config = get_ai_config()
                analysis_params = ai_config.get("analysis_params", {})
                shap_max_rows = analysis_params.get("shap_max_rows", 100)

                # SHAP 계산을 위해 데이터 크기 제한
                X_sample = X.head(shap_max_rows) if len(X) > shap_max_rows else X
                
                if isinstance(X_sample, pd.DataFrame):
                    X_array = X_sample.values
                else:
                    X_array = X_sample
                
                explainer = shap.TreeExplainer(self.model)
                shap_values = explainer.shap_values(X_array)
                
                return shap_values
                
            except ImportError:
                print("경고: 특성 중요도를 위해 SHAP을 사용할 수 없습니다.")
                return None
            except Exception as e:
                print(f"경고: SHAP 계산 실패: {e}")
                return None
        
        return None


def create_anomaly_detector(model_name: str = 'iforest', **kwargs) -> AnomalyDetector:
    """
    이상 탐지기를 생성하는 팩토리 함수입니다.
    
    Args:
        model_name: 생성할 모델의 이름
        **kwargs: 모델별 파라미터
        
    Returns:
        구성된 AnomalyDetector 인스턴스
    """
    return AnomalyDetector(model_name=model_name, model_params=kwargs)