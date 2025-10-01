"""
Main analysis service that orchestrates the anomaly detection pipeline.

This module provides the main interface for running complete anomaly detection
analysis, combining preprocessing, model training, and result generation.
"""

import os
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
import joblib

from ..core.exceptions import AnomalyDetectionError
from ..core.config import config
from ..pipelines.preprocessing import DataPreprocessor
from ..pipelines.detection import AnomalyDetector
from ..services.file_service import FileService
from ..restore import restore_and_save_readable_anomalies
from ..visualize_graph import (
    plot_anomaly_by_hour,
    plot_anomaly_by_user,
    plot_anomaly_score_distribution
)


class AnalysisService:
    """High-level service for complete anomaly detection analysis."""
    
    def __init__(self):
        self.preprocessor = DataPreprocessor()
        self.detector = AnomalyDetector()
        self.file_service = FileService()
    
    def run_complete_analysis(
        self,
        file_path: str,
        exclude_columns: Optional[List[str]] = None,
        user_col: Optional[str] = None,
        time_col: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run complete anomaly detection analysis.
        
        Args:
            file_path: Path to the input CSV file
            exclude_columns: Columns to exclude from analysis
            user_col: User identifier column name
            time_col: Time/timestamp column name
            
        Returns:
            Dictionary containing analysis results
        """
        try:
            # Step 1: Load and validate data
            print("Step 1: Loading data...")
            data = self.file_service.read_csv_file(file_path)
            
            # Handle user and time columns
            user_col, time_col = self._prepare_special_columns(data, user_col, time_col)
            
            # Step 2: Prepare data for modeling (exclude user column from features)
            print("Step 2: Preparing data for modeling...")
            model_data = self._prepare_model_data(data, exclude_columns, user_col)
            
            # Step 3: Preprocess data
            print("Step 3: Preprocessing data...")
            processed_data, categorical_cols, encoder = self.preprocessor.fit_transform(
                model_data, exclude_columns
            )
            
            # Step 4: Train model and predict
            print("Step 4: Training model and detecting anomalies...")
            predictions, scores = self.detector.fit_predict(processed_data)
            
            # Step 5: Combine results with original data
            print("Step 5: Combining results...")
            results_df = self._combine_results(data, processed_data, predictions, scores)
            
            # Step 6: Save intermediate files
            print("Step 6: Saving intermediate files...")
            file_paths = self._save_intermediate_files(
                file_path, processed_data, predictions, scores, encoder
            )
            
            # Step 7: Restore readable results
            print("Step 7: Creating readable results...")
            final_results_path = self._create_readable_results(
                file_paths['full_results'], encoder, file_path
            )
            
            # Step 8: Generate visualizations
            print("Step 8: Generating visualizations...")
            visualizations = self._generate_visualizations(
                final_results_path, user_col, time_col
            )
            
            # Step 9: Create summary
            print("Step 9: Creating analysis summary...")
            summary = self._create_analysis_summary(
                results_df, user_col, time_col
            )
            
            # Step 10: Prepare final results
            final_results = self._prepare_final_results(
                results_df, final_results_path, summary, visualizations,
                user_col, time_col
            )
            
            print(f"Analysis completed successfully!")
            return final_results
            
        except Exception as e:
            raise AnomalyDetectionError(f"Analysis failed: {str(e)}")
    
    def _prepare_special_columns(
        self, 
        data: pd.DataFrame, 
        user_col: Optional[str], 
        time_col: Optional[str]
    ) -> Tuple[str, Optional[str]]:
        """Prepare user and time columns."""
        # Handle user column
        if user_col is None or user_col == "":
            data['user'] = 'all'
            user_col = 'user'
        
        # Handle time column
        if time_col is None or time_col == "":
            time_col = None
        
        return user_col, time_col
    
    def _prepare_model_data(
        self, 
        data: pd.DataFrame, 
        exclude_columns: Optional[List[str]], 
        user_col: str
    ) -> pd.DataFrame:
        """Prepare data for modeling by excluding user column."""
        model_data = data.copy()
        
        # Remove user column from model features
        if user_col in model_data.columns:
            model_data = model_data.drop(columns=[user_col])
        
        return model_data
    
    def _combine_results(
        self,
        original_data: pd.DataFrame,
        processed_data: pd.DataFrame,
        predictions: np.ndarray,
        scores: np.ndarray
    ) -> pd.DataFrame:
        """Combine original data with model results."""
        results = processed_data.copy().reset_index(drop=True)
        results['Anomaly'] = predictions
        results['Anomaly_Score'] = scores
        
        # Sort by anomaly score (descending)
        results = results.sort_values(by='Anomaly_Score', ascending=False).reset_index(drop=True)
        
        return results
    
    def _save_intermediate_files(
        self,
        original_file_path: str,
        processed_data: pd.DataFrame,
        predictions: np.ndarray,
        scores: np.ndarray,
        encoder
    ) -> Dict[str, str]:
        """Save intermediate files for SHAP and other analyses."""
        base_filename = original_file_path.replace('.csv', '')
        
        # Save model
        model_path = f"{base_filename}_model.pkl"
        self.detector.save_model(model_path)
        
        # Save SHAP input data (limit size)
        shap_input = processed_data.head(config.model.shap_max_rows)
        shap_input = shap_input.round(6)  # Reduce precision to save space
        shap_input_path = f"{base_filename}_X_for_shap.csv"
        shap_input.to_csv(shap_input_path, index=False)
        
        # Save SHAP values
        shap_values = self.detector.get_feature_importance(processed_data)
        if shap_values is not None:
            shap_values_path = f"{base_filename}_shap_values.npy"
            np.save(shap_values_path, shap_values)
        
        # Combine results with original data for full results
        results_with_predictions = processed_data.copy()
        results_with_predictions['Anomaly'] = predictions
        results_with_predictions['Anomaly_Score'] = scores
        
        full_results_path = f"{base_filename}_full_data_with_anomaly_info.csv"
        results_with_predictions.to_csv(full_results_path, index=False)
        
        return {
            'model': model_path,
            'shap_input': shap_input_path,
            'full_results': full_results_path
        }
    
    def _create_readable_results(
        self,
        full_results_path: str,
        encoder,
        original_file_path: str
    ) -> str:
        """Create human-readable results by restoring encoded values."""
        if encoder is not None:
            readable_path = original_file_path.replace('.csv', '_full_data_with_anomaly_info_readable.csv')
            restore_and_save_readable_anomalies(
                anomaly_csv_path=full_results_path,
                encoder_mapping_dict=encoder.mapping,
                output_path=readable_path
            )
            return readable_path
        else:
            print("No encoder available, skipping restoration step")
            return full_results_path
    
    def _generate_visualizations(
        self,
        results_path: str,
        user_col: str,
        time_col: Optional[str]
    ) -> Dict[str, Optional[str]]:
        """Generate visualization HTML."""
        try:
            df_full = pd.read_csv(results_path)
            
            # Clean up column names (remove .1 suffixes)
            for col in df_full.columns:
                if col.endswith('.1'):
                    orig_col = col[:-2]
                    if orig_col in df_full.columns:
                        df_full.drop(columns=[orig_col], inplace=True)
                    df_full.rename(columns={col: orig_col}, inplace=True)
            
            # Generate visualizations for anomalies only
            anomalies_df = df_full[df_full['Anomaly'] == 1]
            
            visualizations = {}
            
            # Score distribution
            visualizations['score_distribution'] = plot_anomaly_score_distribution(
                df_full, threshold=config.ui.default_threshold, score_col='Anomaly_Score'
            )
            
            # User-based visualization
            visualizations['user_graph'] = plot_anomaly_by_user(
                anomalies_df, user_col=user_col
            )
            
            # Time-based visualization (if time column exists)
            if time_col is not None and time_col in df_full.columns:
                visualizations['hour_graph'] = plot_anomaly_by_hour(
                    anomalies_df, user_col=user_col, time_col=time_col
                )
            else:
                visualizations['hour_graph'] = None
                print("Time column not available, skipping time-based visualization")
            
            return visualizations
            
        except Exception as e:
            print(f"Visualization generation failed: {e}")
            return {
                'score_distribution': None,
                'user_graph': None,
                'hour_graph': None
            }
    
    def _create_analysis_summary(
        self,
        results_df: pd.DataFrame,
        user_col: str,
        time_col: Optional[str]
    ) -> Dict[str, Any]:
        """Create analysis summary and description."""
        from ..ai_script import generate_description  # Import here to avoid circular imports
        
        total_count = len(results_df)
        anomaly_count = int(results_df['Anomaly'].sum())
        
        # Create description HTML
        anomalies_only = results_df[results_df['Anomaly'] == 1] if anomaly_count > 0 else pd.DataFrame()
        
        if not anomalies_only.empty:
            description_html = generate_description(anomalies_only, user_col, time_col)
        else:
            description_html = "<div>No anomalies detected in the dataset.</div>"
        
        return {
            'total_count': total_count,
            'anomaly_count': anomaly_count,
            'summary_text': f"이상치 {anomaly_count:,}건 / 전체 {total_count:,}건",
            'description_html': description_html
        }
    
    def _prepare_final_results(
        self,
        results_df: pd.DataFrame,
        final_results_path: str,
        summary: Dict[str, Any],
        visualizations: Dict[str, Optional[str]],
        user_col: str,
        time_col: Optional[str]
    ) -> Dict[str, Any]:
        """Prepare final results dictionary."""
        # Load final results for output
        df_full = pd.read_csv(final_results_path)
        
        # Extract anomalies and prepare data for frontend
        detected_anomalies = df_full[df_full['Anomaly'] == 1]
        
        # Remove TF-IDF columns for display
        tfidf_cols = [col for col in detected_anomalies.columns if '_tfidf_' in col]
        detected_for_display = detected_anomalies.drop(columns=tfidf_cols, errors='ignore')
        
        # Get top results for preview
        preview_top100 = detected_for_display.sort_values(
            by="Anomaly_Score", ascending=False
        ).head(config.model.max_preview_rows)
        
        # Prepare table HTML
        if len(preview_top100) > 0:
            table_html = preview_top100.to_html(index=False, classes="table table-sm")
        else:
            table_html = "<p>이상치가 없습니다.</p>"
        
        # Clean data for JSON serialization
        def clean_for_json(obj):
            """Clean data for JSON serialization."""
            if isinstance(obj, dict):
                return {k: clean_for_json(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [clean_for_json(v) for v in obj]
            elif pd.isna(obj):
                return None
            elif isinstance(obj, (np.integer, np.int64, np.int32)):
                return int(obj)
            elif isinstance(obj, (np.floating, np.float64, np.float32)):
                return float(obj)
            elif isinstance(obj, np.bool_):
                return bool(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            else:
                return obj
        
        # Prepare records for download
        anomaly_records = clean_for_json(
            detected_for_display.head(config.model.max_preview_rows).to_dict(orient="records")
        )
        all_records = clean_for_json(
            df_full.drop(columns=tfidf_cols, errors='ignore').head(config.model.max_preview_rows).to_dict(orient="records")
        )
        
        # Also save detected anomalies separately
        base_filename = final_results_path.replace('.csv', '').replace('_full_data_with_anomaly_info_readable', '')
        detected_anomalies_path = f"{base_filename}_pyod_detected_anomalies.csv"
        detected_anomalies.to_csv(detected_anomalies_path, index=False)
        
        return {
            "summary": summary['summary_text'],
            "anomaly_count": summary['anomaly_count'],
            "total": summary['total_count'],
            "table_html": table_html,
            "records": anomaly_records,
            "all_records": all_records,
            "user_col": user_col,
            "time_col": time_col,
            "columns": [str(col) for col in df_full.columns],
            "result_csv_path": final_results_path,
            "text_html": summary['description_html'],
            "score_distribution_html": visualizations['score_distribution'],
            "user_graph_html": visualizations['user_graph'],
            "hour_graph_html": visualizations['hour_graph'],
        }


def detect_anomalies(file_path: str, exclude_columns: Optional[List[str]] = None, 
                   user_col: Optional[str] = None, time_col: Optional[str] = None) -> Dict[str, Any]:
    """
    Legacy function for backward compatibility.
    
    This function maintains the original API while using the new modular approach.
    
    Args:
        file_path: Path to the input CSV file
        exclude_columns: Columns to exclude from analysis
        user_col: User identifier column name
        time_col: Time/timestamp column name
        
    Returns:
        Dictionary containing analysis results
    """
    service = AnalysisService()
    return service.run_complete_analysis(file_path, exclude_columns, user_col, time_col)