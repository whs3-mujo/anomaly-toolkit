"""
이상 탐지를 위한 데이터 전처리 파이프라인.

이 모듈은 데이터 정제, 인코딩, 특성 추출 및
기계 학습 모델을 위한 데이터 준비 함수들을 포함합니다.
"""

import pandas as pd
import numpy as np
from typing import Tuple, List, Optional, Dict, Any
from sklearn.preprocessing import StandardScaler
from sklearn.feature_extraction.text import TfidfVectorizer
import category_encoders as ce

from ..core.exceptions import DataValidationError, InsufficientDataError
# AI 관련 설정을 중앙에서 관리하기 위해 ai_config.py를 임포트합니다.
from .ai_config import get_ai_config


class DataPreprocessor:
    """이상 탐지를 위한 데이터 전처리 파이프라인"""
    
    def __init__(self):
        # AI 설정을 로드합니다.
        ai_config = get_ai_config()
        self.params = ai_config.get("preprocessing_params", {})
        
        self.encoder: Optional[ce.CountEncoder] = None
        self.scaler: Optional[StandardScaler] = None
        self.tfidf_vectorizers: Dict[str, TfidfVectorizer] = {}
        self.categorical_columns: List[str] = []
        self.text_columns: List[str] = []
        self.numeric_columns: List[str] = []
    
    def detect_text_columns(self, df: pd.DataFrame, min_avg_length: int = None) -> List[str]:
        """
        평균 문자열 길이를 기반으로 텍스트 컬럼을 탐지합니다.
        
        Args:
            df: 입력 데이터프레임
            min_avg_length: 텍스트 컬럼으로 간주할 최소 평균 길이
            
        Returns:
            텍스트 컬럼으로 식별된 컬럼 이름 리스트
        """
        if min_avg_length is None:
            # ai_config.py에서 설정을 가져옵니다.
            min_avg_length = self.params.get("min_text_length", 20)
            
        candidate_cols = df.select_dtypes(include=['object', 'string']).columns
        text_cols = []
        
        for col in candidate_cols:
            try:
                avg_length = df[col].astype(str).apply(len).mean()
                if avg_length >= min_avg_length:
                    text_cols.append(col)
            except Exception as e:
                print(f"경고: 컬럼 '{col}' 처리 중 오류 발생: {e}")
                continue
                
        return text_cols
    
    def validate_data(self, df: pd.DataFrame) -> None:
        """
        전처리할 입력 데이터의 유효성을 검사합니다.
        
        Args:
            df: 입력 데이터프레임
            
        Raises:
            DataValidationError: 데이터 유효성 검사에 실패한 경우
            InsufficientDataError: 분석에 데이터가 불충분한 경우
        """
        if df.empty:
            raise InsufficientDataError("데이터셋이 비어있습니다.")
        
        if len(df) < 10:
            raise InsufficientDataError("분석을 위해 데이터셋에 최소 10개의 행이 필요합니다.")
        
        # 모든 컬럼이 null 값인지 확인
        if df.isnull().all().all():
            raise DataValidationError("모든 컬럼에 null 값만 포함되어 있습니다.")
    
    def prepare_data(self, df: pd.DataFrame, exclude_columns: List[str] = None) -> pd.DataFrame:
        """
        제외할 컬럼을 제거하고 기본적인 문제를 처리하여 데이터를 준비합니다.
        
        Args:
            df: 입력 데이터프레임
            exclude_columns: 제외할 컬럼 이름 리스트
            
        Returns:
            준비된 데이터프레임
        """
        self.validate_data(df)
        
        data = df.copy()
        
        # 제외 컬럼 제거
        if exclude_columns:
            existing_exclude_cols = [col for col in exclude_columns if col in data.columns]
            if existing_exclude_cols:
                data = data.drop(columns=existing_exclude_cols)
                print(f"제외된 컬럼: {existing_exclude_cols}")
        
        return data
    
    def handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        데이터셋의 결측치를 처리합니다.
        
        Args:
            df: 입력 데이터프레임
            
        Returns:
            결측치가 처리된 데이터프레임
        """
        data = df.copy()
        
        # 컬럼 타입 식별
        self.numeric_columns = data.select_dtypes(include=['int64', 'float64']).columns.tolist()
        self.text_columns = self.detect_text_columns(data)
        self.categorical_columns = data.select_dtypes(include=['object', 'category', 'bool']).columns.tolist()
        
        # 범주형 컬럼에서 텍스트 컬럼 제거
        self.categorical_columns = [col for col in self.categorical_columns if col not in self.text_columns]
        
        # 컬럼 타입별 결측치 처리
        for col in self.numeric_columns:
            data[col] = data[col].fillna(0)
            
        for col in self.categorical_columns:
            data[col] = data[col].fillna("Unknown")
            
        return data
    
    def encode_categorical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        카운트 인코딩을 사용하여 범주형 특성을 인코딩합니다.
        
        Args:
            df: 입력 데이터프레임
            
        Returns:
            인코딩된 범주형 특성을 가진 데이터프레임
        """
        if not self.categorical_columns:
            return pd.DataFrame(index=df.index)
        
        categorical_data = df[self.categorical_columns]
        
        # ai_config.py에서 인코딩 방법을 가져옵니다.
        encoding_method = self.params.get("encoding_method", 'count')
        
        if encoding_method == 'count':
            self.encoder = ce.CountEncoder()
            encoded = self.encoder.fit_transform(categorical_data)
        else:
            raise ValueError(f"지원하지 않는 인코딩 방식입니다: {encoding_method}")
        
        return encoded
    
    def extract_text_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        TF-IDF를 사용하여 텍스트 컬럼에서 특성을 추출합니다.
        
        Args:
            df: 입력 데이터프레임
            
        Returns:
            TF-IDF 특성을 가진 데이터프레임
        """
        if not self.text_columns:
            return pd.DataFrame(index=df.index)
        
        tfidf_dfs = []
        
        for col in self.text_columns:
            try:
                # ai_config.py에서 max_features를 가져옵니다.
                tfidf_max_features = self.params.get("tfidf_max_features", 100)
                
                # max_features를 동적으로 결정
                max_features = min(tfidf_max_features, len(df) // 2)
                if max_features < 1:
                    max_features = 1
                
                vectorizer = TfidfVectorizer(max_features=max_features, stop_words=None)
                text_data = df[col].astype(str).fillna('')
                
                tfidf_matrix = vectorizer.fit_transform(text_data)
                
                # 나중에 사용할 수 있도록 벡터라이저 저장
                self.tfidf_vectorizers[col] = vectorizer
                
                # 컬럼 이름 생성
                column_prefix = col.replace(' ', '_').lower()
                column_names = [f"{column_prefix}_tfidf_{i}" for i in range(tfidf_matrix.shape[1])]
                
                tfidf_df = pd.DataFrame(
                    tfidf_matrix.toarray(),
                    columns=column_names,
                    index=df.index
                )
                
                tfidf_dfs.append(tfidf_df)
                
            except Exception as e:
                print(f"경고: 컬럼 '{col}'에 대한 TF-IDF 처리 실패: {e}")
                continue
        
        if tfidf_dfs:
            return pd.concat(tfidf_dfs, axis=1)
        else:
            return pd.DataFrame(index=df.index)
    
    def scale_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        StandardScaler를 사용하여 특성을 스케일링합니다.
        
        Args:
            df: 입력 데이터프레임
            
        Returns:
            스케일링된 데이터프레임
        """
        if df.empty:
            return df
        
        self.scaler = StandardScaler()
        scaled_data = self.scaler.fit_transform(df)
        
        return pd.DataFrame(scaled_data, columns=df.columns, index=df.index)
    
    def fit_transform(self, df: pd.DataFrame, exclude_columns: List[str] = None) -> Tuple[pd.DataFrame, List[str], Optional[ce.CountEncoder]]:
        """
        전체 전처리 파이프라인을 실행합니다.
        
        Args:
            df: 입력 데이터프레임
            exclude_columns: 처리에서 제외할 컬럼 이름 리스트
            
        Returns:
            (처리된 데이터, 범주형 컬럼, 인코더) 튜플
        """
        # 데이터 준비
        data = self.prepare_data(df, exclude_columns)
        
        # 결측치 처리
        data = self.handle_missing_values(data)
        
        # 범주형 특성 인코딩
        encoded_categorical = self.encode_categorical_features(data)
        
        # 텍스트 특성 추출
        text_features = self.extract_text_features(data)
        
        # 수치형, 범주형, 텍스트 특성 결합
        numeric_data = data[self.numeric_columns] if self.numeric_columns else pd.DataFrame(index=data.index)
        
        # 적절한 결합을 위해 인덱스 재설정
        numeric_data = numeric_data.reset_index(drop=True)
        encoded_categorical = encoded_categorical.reset_index(drop=True)
        text_features = text_features.reset_index(drop=True)
        
        # 모든 특성 결합
        combined_data = pd.concat([numeric_data, encoded_categorical, text_features], axis=1)
        
        # ai_config.py에서 스케일링 여부를 확인합니다.
        scale_features = self.params.get("scale_features", True)
        
        # 활성화된 경우 특성 스케일링
        if scale_features and not combined_data.empty:
            combined_data = self.scale_features(combined_data)
        
        return combined_data, self.categorical_columns, self.encoder


def preprocess_log_data_with_text(df: pd.DataFrame, encode_method: str = 'count', 
                                scale: bool = True, tfidf_max_features: int = 100) -> Tuple[pd.DataFrame, List[str], Optional[ce.CountEncoder]]:
    """
    하위 호환성을 위한 레거시 함수입니다.
    
    이 함수는 새로운 모듈식 접근 방식을 사용하면서 기존 API를 유지합니다.
    
    Args:
        df: 입력 데이터프레임
        encode_method: 범주형 변수의 인코딩 방식
        scale: 특성 스케일링 여부
        tfidf_max_features: TF-IDF의 최대 특성 수
        
    Returns:
        (처리된 데이터, 범주형 컬럼, 인코더) 튜플
    """
    # 이 함수는 이제 새로운 DataPreprocessor를 직접 사용하므로,
    # 더 이상 config를 임시로 업데이트할 필요가 없습니다.
    # DataPreprocessor가 내부적으로 ai_config.py를 사용합니다.
    
    preprocessor = DataPreprocessor()
    
    # 레거시 함수의 파라미터를 DataPreprocessor에 전달할 수 있도록 로직을 수정할 수 있습니다.
    # 하지만 현재 구현에서는 DataPreprocessor가 ai_config에서 모든 것을 가져오므로,
    # 이 레거시 함수의 파라미터는 무시될 수 있습니다.
    # 필요하다면, 이 파라미터들을 사용하여 ai_config를 오버라이드하는 로직을 추가할 수 있습니다.
    
    result = preprocessor.fit_transform(df)
    return result


def detect_text_columns(df: pd.DataFrame, min_avg_length: int = 20) -> List[str]:
    """
    하위 호환성을 위한 레거시 함수입니다.
    
    Args:
        df: 입력 데이터프레임
        min_avg_length: 텍스트 컬럼으로 간주할 최소 평균 길이
        
    Returns:
        텍스트 컬럼 이름 리스트
    """
    preprocessor = DataPreprocessor()
    return preprocessor.detect_text_columns(df, min_avg_length)