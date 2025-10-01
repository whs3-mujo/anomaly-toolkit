"""
File handling services for the anomaly detection system.

This module provides services for file upload, encoding detection,
and file format validation.
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
    """Handles file operations for anomaly detection."""
    
    @staticmethod
    def detect_encoding(file_path: str) -> str:
        """
        Detect file encoding automatically.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Detected encoding string
            
        Raises:
            EncodingDetectionError: If encoding detection fails
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
                    
                    print(f"Detected encoding: {encoding} (confidence: {confidence:.2f})")
                    
                    # Use detected encoding if confidence is reasonable
                    if confidence > 0.7:
                        return encoding
                    else:
                        print(f"Low confidence in detected encoding, using default: {config.system.default_encoding}")
                        return config.system.default_encoding
                else:
                    return config.system.default_encoding
                    
        except Exception as e:
            raise EncodingDetectionError(f"Failed to detect file encoding: {str(e)}")
    
    @staticmethod
    def read_csv_file(file_path: str, encoding: str = None) -> pd.DataFrame:
        """
        Read CSV file with automatic encoding detection.
        
        Args:
            file_path: Path to the CSV file
            encoding: Specific encoding to use (optional)
            
        Returns:
            DataFrame containing the CSV data
            
        Raises:
            FileProcessingError: If file reading fails
        """
        if encoding is None:
            encoding = FileService.detect_encoding(file_path)
        
        try:
            df = pd.read_csv(file_path, encoding=encoding)
            
            if df.empty:
                raise FileProcessingError("CSV file is empty")
            
            print(f"Successfully loaded CSV file: {len(df)} rows, {len(df.columns)} columns")
            return df
            
        except pd.errors.EmptyDataError:
            raise FileProcessingError("CSV file contains no data")
        except pd.errors.ParserError as e:
            raise FileProcessingError(f"CSV parsing error: {str(e)}")
        except UnicodeDecodeError as e:
            raise FileProcessingError(f"Encoding error with {encoding}: {str(e)}")
        except Exception as e:
            raise FileProcessingError(f"Failed to read CSV file: {str(e)}")
    
    @staticmethod
    def save_uploaded_file(uploaded_file, upload_dir: str = None) -> str:
        """
        Save uploaded file to disk.
        
        Args:
            uploaded_file: Django uploaded file object
            upload_dir: Directory to save the file (optional)
            
        Returns:
            Path to the saved file
            
        Raises:
            FileProcessingError: If file saving fails
        """
        if upload_dir is None:
            upload_dir = os.path.join(settings.MEDIA_ROOT, "uploads")
        
        try:
            # Create upload directory if it doesn't exist
            os.makedirs(upload_dir, exist_ok=True)
            
            # Generate file path
            file_path = os.path.join(upload_dir, uploaded_file.name)
            
            # Save file
            with open(file_path, "wb+") as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
            
            print(f"File saved successfully: {file_path}")
            return file_path
            
        except Exception as e:
            raise FileProcessingError(f"Failed to save uploaded file: {str(e)}")
    
    @staticmethod
    def validate_csv_file(uploaded_file) -> bool:
        """
        Validate uploaded CSV file.
        
        Args:
            uploaded_file: Django uploaded file object
            
        Returns:
            True if file is valid
            
        Raises:
            FileProcessingError: If validation fails
        """
        # Check file extension
        if not uploaded_file.name.lower().endswith('.csv'):
            raise FileProcessingError("Only CSV files are allowed")
        
        # Check file size
        max_size = config.ui.max_file_size_mb * 1024 * 1024  # Convert to bytes
        if uploaded_file.size > max_size:
            raise FileProcessingError(f"File size exceeds {config.ui.max_file_size_mb}MB limit")
        
        return True
    
    @staticmethod
    def get_file_preview(file_path: str, num_rows: int = 5) -> Tuple[pd.DataFrame, list]:
        """
        Get preview of CSV file content.
        
        Args:
            file_path: Path to the CSV file
            num_rows: Number of rows to preview
            
        Returns:
            Tuple of (preview_dataframe, column_names)
            
        Raises:
            FileProcessingError: If preview generation fails
        """
        try:
            df = FileService.read_csv_file(file_path)
            
            preview_df = df.head(num_rows)
            column_names = df.columns.tolist()
            
            return preview_df, column_names
            
        except Exception as e:
            raise FileProcessingError(f"Failed to generate file preview: {str(e)}")