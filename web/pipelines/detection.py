"""
Anomaly detection pipeline using PyOD models.

This module provides a modular interface for anomaly detection using various
PyOD models with consistent input/output interfaces.
"""

import pandas as pd
import numpy as np
from typing import Tuple, Dict, Any, Optional
import joblib
from pyod.models.iforest import IForest

from ..core.exceptions import ModelTrainingError
from ..core.config import config


class AnomalyDetector:
    """Modular anomaly detection using PyOD models."""
    
    def __init__(self, model_name: str = 'iforest', model_params: Dict[str, Any] = None):
        """
        Initialize the anomaly detector.
        
        Args:
            model_name: Name of the model to use
            model_params: Model-specific parameters
        """
        self.model_name = model_name
        self.model_params = model_params or config.get_model_params()
        self.model = None
        self.is_fitted = False
    
    def _create_model(self):
        """Create the anomaly detection model based on model_name."""
        if self.model_name == 'iforest':
            self.model = IForest(
                contamination=self.model_params.get('contamination', 0.05),
                random_state=self.model_params.get('random_state', 42),
                n_estimators=self.model_params.get('n_estimators', 100)
            )
        else:
            raise ValueError(f"Unsupported model: {self.model_name}")
    
    def fit(self, X: pd.DataFrame) -> 'AnomalyDetector':
        """
        Fit the anomaly detection model.
        
        Args:
            X: Training data
            
        Returns:
            Self for method chaining
            
        Raises:
            ModelTrainingError: If model training fails
        """
        try:
            if self.model is None:
                self._create_model()
            
            # Convert to numpy array if needed
            if isinstance(X, pd.DataFrame):
                X_array = X.values
            else:
                X_array = X
            
            self.model.fit(X_array)
            self.is_fitted = True
            
            return self
            
        except Exception as e:
            raise ModelTrainingError(f"Model training failed: {str(e)}")
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict anomalies.
        
        Args:
            X: Input data
            
        Returns:
            Binary predictions (1 for anomaly, 0 for normal)
            
        Raises:
            ModelTrainingError: If model is not fitted
        """
        if not self.is_fitted:
            raise ModelTrainingError("Model must be fitted before prediction")
        
        # Convert to numpy array if needed
        if isinstance(X, pd.DataFrame):
            X_array = X.values
        else:
            X_array = X
        
        return self.model.predict(X_array)
    
    def decision_function(self, X: pd.DataFrame) -> np.ndarray:
        """
        Calculate anomaly scores.
        
        Args:
            X: Input data
            
        Returns:
            Anomaly scores
            
        Raises:
            ModelTrainingError: If model is not fitted
        """
        if not self.is_fitted:
            raise ModelTrainingError("Model must be fitted before scoring")
        
        # Convert to numpy array if needed
        if isinstance(X, pd.DataFrame):
            X_array = X.values
        else:
            X_array = X
        
        return self.model.decision_function(X_array)
    
    def fit_predict(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Fit the model and predict anomalies in one step.
        
        Args:
            X: Input data
            
        Returns:
            Tuple of (predictions, scores)
        """
        self.fit(X)
        predictions = self.predict(X)
        scores = self.decision_function(X)
        
        return predictions, scores
    
    def save_model(self, filepath: str) -> None:
        """
        Save the trained model to file.
        
        Args:
            filepath: Path to save the model
        """
        if not self.is_fitted:
            raise ModelTrainingError("Cannot save unfitted model")
        
        joblib.dump(self.model, filepath)
    
    def load_model(self, filepath: str) -> 'AnomalyDetector':
        """
        Load a trained model from file.
        
        Args:
            filepath: Path to load the model from
            
        Returns:
            Self for method chaining
        """
        self.model = joblib.load(filepath)
        self.is_fitted = True
        return self
    
    def get_feature_importance(self, X: pd.DataFrame, method: str = 'shap') -> Optional[np.ndarray]:
        """
        Get feature importance scores.
        
        Args:
            X: Input data
            method: Method to calculate importance ('shap' supported)
            
        Returns:
            Feature importance scores or None if not available
        """
        if not self.is_fitted:
            raise ModelTrainingError("Model must be fitted before getting feature importance")
        
        if method == 'shap':
            try:
                import shap
                
                # Limit data size for SHAP calculation
                X_sample = X.head(config.model.shap_max_rows) if len(X) > config.model.shap_max_rows else X
                
                if isinstance(X_sample, pd.DataFrame):
                    X_array = X_sample.values
                else:
                    X_array = X_sample
                
                explainer = shap.TreeExplainer(self.model)
                shap_values = explainer.shap_values(X_array)
                
                return shap_values
                
            except ImportError:
                print("Warning: SHAP not available for feature importance")
                return None
            except Exception as e:
                print(f"Warning: SHAP calculation failed: {e}")
                return None
        
        return None


def create_anomaly_detector(model_name: str = 'iforest', **kwargs) -> AnomalyDetector:
    """
    Factory function to create anomaly detectors.
    
    Args:
        model_name: Name of the model to create
        **kwargs: Model-specific parameters
        
    Returns:
        Configured AnomalyDetector instance
    """
    return AnomalyDetector(model_name=model_name, model_params=kwargs)