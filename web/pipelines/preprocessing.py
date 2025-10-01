"""
Data preprocessing pipeline for anomaly detection.

This module contains functions for data cleaning, encoding, feature extraction,
and preparation for machine learning models.
"""

import pandas as pd
import numpy as np
from typing import Tuple, List, Optional, Dict, Any
from sklearn.preprocessing import StandardScaler
from sklearn.feature_extraction.text import TfidfVectorizer
import category_encoders as ce

from ..core.exceptions import DataValidationError, InsufficientDataError
from ..core.config import config


class DataPreprocessor:
    """Handles data preprocessing for anomaly detection."""
    
    def __init__(self):
        self.encoder: Optional[ce.CountEncoder] = None
        self.scaler: Optional[StandardScaler] = None
        self.tfidf_vectorizers: Dict[str, TfidfVectorizer] = {}
        self.categorical_columns: List[str] = []
        self.text_columns: List[str] = []
        self.numeric_columns: List[str] = []
    
    def detect_text_columns(self, df: pd.DataFrame, min_avg_length: int = None) -> List[str]:
        """
        Detect text columns based on average string length.
        
        Args:
            df: Input DataFrame
            min_avg_length: Minimum average length to consider a column as text
            
        Returns:
            List of column names identified as text columns
        """
        if min_avg_length is None:
            min_avg_length = config.model.min_text_length
            
        candidate_cols = df.select_dtypes(include=['object', 'string']).columns
        text_cols = []
        
        for col in candidate_cols:
            try:
                avg_length = df[col].astype(str).apply(len).mean()
                if avg_length >= min_avg_length:
                    text_cols.append(col)
            except Exception as e:
                print(f"Warning: Error processing column '{col}': {e}")
                continue
                
        return text_cols
    
    def validate_data(self, df: pd.DataFrame) -> None:
        """
        Validate input data for preprocessing.
        
        Args:
            df: Input DataFrame
            
        Raises:
            DataValidationError: If data validation fails
            InsufficientDataError: If data is insufficient for analysis
        """
        if df.empty:
            raise InsufficientDataError("Dataset is empty")
        
        if len(df) < 10:
            raise InsufficientDataError("Dataset must have at least 10 rows for analysis")
        
        # Check if all columns are null
        if df.isnull().all().all():
            raise DataValidationError("All columns contain only null values")
    
    def prepare_data(self, df: pd.DataFrame, exclude_columns: List[str] = None) -> pd.DataFrame:
        """
        Prepare data by removing excluded columns and handling basic issues.
        
        Args:
            df: Input DataFrame
            exclude_columns: List of column names to exclude
            
        Returns:
            Prepared DataFrame
        """
        self.validate_data(df)
        
        data = df.copy()
        
        # Remove excluded columns
        if exclude_columns:
            existing_exclude_cols = [col for col in exclude_columns if col in data.columns]
            if existing_exclude_cols:
                data = data.drop(columns=existing_exclude_cols)
                print(f"Excluded columns: {existing_exclude_cols}")
        
        return data
    
    def handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Handle missing values in the dataset.
        
        Args:
            df: Input DataFrame
            
        Returns:
            DataFrame with missing values handled
        """
        data = df.copy()
        
        # Identify column types
        self.numeric_columns = data.select_dtypes(include=['int64', 'float64']).columns.tolist()
        self.text_columns = self.detect_text_columns(data)
        self.categorical_columns = data.select_dtypes(include=['object', 'category', 'bool']).columns.tolist()
        
        # Remove text columns from categorical columns
        self.categorical_columns = [col for col in self.categorical_columns if col not in self.text_columns]
        
        # Handle missing values by column type
        for col in self.numeric_columns:
            data[col] = data[col].fillna(0)
            
        for col in self.categorical_columns:
            data[col] = data[col].fillna("Unknown")
            
        return data
    
    def encode_categorical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Encode categorical features using count encoding.
        
        Args:
            df: Input DataFrame
            
        Returns:
            DataFrame with encoded categorical features
        """
        if not self.categorical_columns:
            return pd.DataFrame(index=df.index)
        
        categorical_data = df[self.categorical_columns]
        
        if config.model.encoding_method == 'count':
            self.encoder = ce.CountEncoder()
            encoded = self.encoder.fit_transform(categorical_data)
        else:
            raise ValueError(f"Unsupported encoding method: {config.model.encoding_method}")
        
        return encoded
    
    def extract_text_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract features from text columns using TF-IDF.
        
        Args:
            df: Input DataFrame
            
        Returns:
            DataFrame with TF-IDF features
        """
        if not self.text_columns:
            return pd.DataFrame(index=df.index)
        
        tfidf_dfs = []
        
        for col in self.text_columns:
            try:
                # Determine max_features dynamically
                max_features = min(config.model.tfidf_max_features, len(df) // 2)
                if max_features < 1:
                    max_features = 1
                
                vectorizer = TfidfVectorizer(max_features=max_features, stop_words=None)
                text_data = df[col].astype(str).fillna('')
                
                tfidf_matrix = vectorizer.fit_transform(text_data)
                
                # Store vectorizer for potential future use
                self.tfidf_vectorizers[col] = vectorizer
                
                # Create column names
                column_prefix = col.replace(' ', '_').lower()
                column_names = [f"{column_prefix}_tfidf_{i}" for i in range(tfidf_matrix.shape[1])]
                
                tfidf_df = pd.DataFrame(
                    tfidf_matrix.toarray(),
                    columns=column_names,
                    index=df.index
                )
                
                tfidf_dfs.append(tfidf_df)
                
            except Exception as e:
                print(f"Warning: TF-IDF processing failed for column '{col}': {e}")
                continue
        
        if tfidf_dfs:
            return pd.concat(tfidf_dfs, axis=1)
        else:
            return pd.DataFrame(index=df.index)
    
    def scale_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Scale features using StandardScaler.
        
        Args:
            df: Input DataFrame
            
        Returns:
            Scaled DataFrame
        """
        if df.empty:
            return df
        
        self.scaler = StandardScaler()
        scaled_data = self.scaler.fit_transform(df)
        
        return pd.DataFrame(scaled_data, columns=df.columns, index=df.index)
    
    def fit_transform(self, df: pd.DataFrame, exclude_columns: List[str] = None) -> Tuple[pd.DataFrame, List[str], Optional[ce.CountEncoder]]:
        """
        Complete preprocessing pipeline.
        
        Args:
            df: Input DataFrame
            exclude_columns: List of column names to exclude from processing
            
        Returns:
            Tuple of (processed_data, categorical_columns, encoder)
        """
        # Prepare data
        data = self.prepare_data(df, exclude_columns)
        
        # Handle missing values
        data = self.handle_missing_values(data)
        
        # Encode categorical features
        encoded_categorical = self.encode_categorical_features(data)
        
        # Extract text features
        text_features = self.extract_text_features(data)
        
        # Combine numeric, categorical, and text features
        numeric_data = data[self.numeric_columns] if self.numeric_columns else pd.DataFrame(index=data.index)
        
        # Reset indices to ensure proper concatenation
        numeric_data = numeric_data.reset_index(drop=True)
        encoded_categorical = encoded_categorical.reset_index(drop=True)
        text_features = text_features.reset_index(drop=True)
        
        # Combine all features
        combined_data = pd.concat([numeric_data, encoded_categorical, text_features], axis=1)
        
        # Scale features if enabled
        if config.model.scale_features and not combined_data.empty:
            combined_data = self.scale_features(combined_data)
        
        return combined_data, self.categorical_columns, self.encoder


def preprocess_log_data_with_text(df: pd.DataFrame, encode_method: str = 'count', 
                                scale: bool = True, tfidf_max_features: int = 100) -> Tuple[pd.DataFrame, List[str], Optional[ce.CountEncoder]]:
    """
    Legacy function for backward compatibility.
    
    This function maintains the original API while using the new modular approach.
    
    Args:
        df: Input DataFrame
        encode_method: Encoding method for categorical variables
        scale: Whether to scale features
        tfidf_max_features: Maximum features for TF-IDF
        
    Returns:
        Tuple of (processed_data, categorical_columns, encoder)
    """
    # Temporarily update config for this call
    original_method = config.model.encoding_method
    original_scale = config.model.scale_features
    original_tfidf = config.model.tfidf_max_features
    
    config.model.encoding_method = encode_method
    config.model.scale_features = scale
    config.model.tfidf_max_features = tfidf_max_features
    
    try:
        preprocessor = DataPreprocessor()
        result = preprocessor.fit_transform(df)
        return result
    finally:
        # Restore original config
        config.model.encoding_method = original_method
        config.model.scale_features = original_scale
        config.model.tfidf_max_features = original_tfidf


def detect_text_columns(df: pd.DataFrame, min_avg_length: int = 20) -> List[str]:
    """
    Legacy function for backward compatibility.
    
    Args:
        df: Input DataFrame
        min_avg_length: Minimum average length to consider a column as text
        
    Returns:
        List of text column names
    """
    preprocessor = DataPreprocessor()
    return preprocessor.detect_text_columns(df, min_avg_length)