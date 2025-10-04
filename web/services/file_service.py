"""
이상 탐지 시스템을 위한 파일 처리 서비스.

이 모듈은 파일 업로드, 인코딩 탐지, 파일 형식 유효성 검사 등의
서비스를 제공합니다.
"""

import os
import pandas as pd
from typing import Optional, Tuple
from django.conf import settings

from ..core.exceptions import FileProcessingError, EncodingDetectionError
from ..core.config import config

try:
    import chardet
except ImportError:
    chardet = None


class FileService:
    """이상 탐지를 위한 파일 관련 작업을 처리합니다."""
    
    @staticmethod
    def detect_encoding(file_path: str) -> str:
        """
        파일 인코딩을 자동으로 탐지합니다.
        
        Args:
            file_path: 파일 경로
            
        Returns:
            탐지된 인코딩 문자열
            
        Raises:
            EncodingDetectionError: 인코딩 탐지에 실패한 경우
        """
        if chardet is None:
            return config.system.default_encoding
        
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read(config.system.encoding_detection_sample_size)
                result = chardet.detect(raw_data)
                
                if result and result['encoding']:
                    confidence = result.get('confidence', 0)
                    encoding = result['encoding']
                    
                    print(f"탐지된 인코딩: {encoding} (신뢰도: {confidence:.2f})")
                    
                    # 신뢰도가 합리적인 경우 탐지된 인코딩 사용
                    if confidence > 0.7:
                        return encoding
                    else:
                        print(f"탐지된 인코딩의 신뢰도가 낮아 기본값 사용: {config.system.default_encoding}")
                        return config.system.default_encoding
                else:
                    return config.system.default_encoding
                    
        except Exception as e:
            raise EncodingDetectionError(f"파일 인코딩 탐지 실패: {str(e)}")
    
    @staticmethod
    def read_csv_file(file_path: str, encoding: str = None) -> pd.DataFrame:
        """
        자동 인코딩 탐지 기능으로 CSV 파일을 읽습니다.
        
        Args:
            file_path: CSV 파일 경로
            encoding: 사용할 특정 인코딩 (선택 사항)
            
        Returns:
            CSV 데이터를 담은 데이터프레임
            
        Raises:
            FileProcessingError: 파일 읽기에 실패한 경우
        """
        if encoding is None:
            encoding = FileService.detect_encoding(file_path)
        
        try:
            df = pd.read_csv(file_path, encoding=encoding)
            
            if df.empty:
                raise FileProcessingError("CSV 파일이 비어있습니다.")
            
            print(f"CSV 파일 로드 성공: {len(df)} 행, {len(df.columns)} 열")
            return df
            
        except pd.errors.EmptyDataError:
            raise FileProcessingError("CSV 파일에 데이터가 없습니다.")
        except pd.errors.ParserError as e:
            raise FileProcessingError(f"CSV 파싱 오류: {str(e)}")
        except UnicodeDecodeError as e:
            raise FileProcessingError(f"{encoding} 인코딩 오류: {str(e)}")
        except Exception as e:
            raise FileProcessingError(f"CSV 파일 읽기 실패: {str(e)}")
    
    @staticmethod
    def save_uploaded_file(uploaded_file, upload_dir: str = None) -> str:
        """
        업로드된 파일을 디스크에 저장합니다.
        
        Args:
            uploaded_file: Django의 업로드된 파일 객체
            upload_dir: 파일을 저장할 디렉토리 (선택 사항)
            
        Returns:
            저장된 파일의 경로
            
        Raises:
            FileProcessingError: 파일 저장에 실패한 경우
        """
        if upload_dir is None:
            upload_dir = os.path.join(settings.MEDIA_ROOT, "uploads")
        
        try:
            # 업로드 디렉토리가 없으면 생성
            os.makedirs(upload_dir, exist_ok=True)
            
            # 파일 경로 생성
            file_path = os.path.join(upload_dir, uploaded_file.name)
            
            # 파일 저장
            with open(file_path, "wb+") as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
            
            print(f"파일 저장 성공: {file_path}")
            return file_path
            
        except Exception as e:
            raise FileProcessingError(f"업로드된 파일 저장 실패: {str(e)}")
    
    @staticmethod
    def validate_csv_file(uploaded_file) -> bool:
        """
        업로드된 CSV 파일의 유효성을 검사합니다.
        
        Args:
            uploaded_file: Django의 업로드된 파일 객체
            
        Returns:
            파일이 유효하면 True
            
        Raises:
            FileProcessingError: 유효성 검사에 실패한 경우
        """
        # 파일 확장자 확인
        if not uploaded_file.name.lower().endswith('.csv'):
            raise FileProcessingError("CSV 파일만 허용됩니다.")
        
        # 파일 크기 확인
        max_size = config.ui.max_file_size_mb * 1024 * 1024  # 바이트로 변환
        if uploaded_file.size > max_size:
            raise FileProcessingError(f"파일 크기가 {config.ui.max_file_size_mb}MB 제한을 초과합니다.")
        
        return True
    
    @staticmethod
    def get_file_preview(file_path: str, num_rows: int = 5) -> Tuple[pd.DataFrame, list]:
        """
        CSV 파일 내용의 미리보기를 가져옵니다.
        
        Args:
            file_path: CSV 파일 경로
            num_rows: 미리 볼 행의 수
            
        Returns:
            (미리보기 데이터프레임, 컬럼 이름 리스트) 튜플
            
        Raises:
            FileProcessingError: 미리보기 생성에 실패한 경우
        """
        try:
            df = FileService.read_csv_file(file_path)
            
            preview_df = df.head(num_rows)
            column_names = df.columns.tolist()
            
            return preview_df, column_names
            
        except Exception as e:
            raise FileProcessingError(f"파일 미리보기 생성 실패: {str(e)}")