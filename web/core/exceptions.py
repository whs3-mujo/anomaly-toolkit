"""
Custom exceptions for the anomaly detection system.

This module defines custom exception classes for better error handling
and debugging throughout the application.
"""


class AnomalyDetectionError(Exception):
    """Base exception for anomaly detection related errors."""
    pass


class DataValidationError(AnomalyDetectionError):
    """Raised when input data validation fails."""
    pass


class FileProcessingError(AnomalyDetectionError):
    """Raised when file processing operations fail."""
    pass


class ModelTrainingError(AnomalyDetectionError):
    """Raised when model training encounters errors."""
    pass


class EncodingDetectionError(AnomalyDetectionError):
    """Raised when file encoding detection fails."""
    pass


class ColumnNotFoundError(DataValidationError):
    """Raised when specified columns are not found in the dataset."""
    pass


class InsufficientDataError(DataValidationError):
    """Raised when dataset doesn't have enough data for analysis."""
    pass