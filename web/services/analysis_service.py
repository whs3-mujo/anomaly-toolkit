"""
이상 탐지 파이프라인을 총괄하는 메인 분석 서비스.

이 모듈은 전처리, 모델 학습, 결과 생성을 결합하여
완전한 이상 탐지 분석을 실행하기 위한 메인 인터페이스를 제공합니다.
"""

import os
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
import joblib

from ..core.exceptions import AnomalyDetectionError
from ..pipelines.preprocessing import DataPreprocessor
from ..pipelines.detection import AnomalyDetector
from ..services.file_service import FileService
from ..restore import restore_and_save_readable_anomalies
from ..visualize_graph import (
    plot_anomaly_by_hour,
    plot_anomaly_by_user,
    plot_anomaly_score_distribution
)
from ..pipelines.ai_config import get_ai_config


class AnalysisService:
    """완전한 이상 탐지 분석을 위한 고수준 서비스입니다."""
    
    def __init__(self):
        self.preprocessor = DataPreprocessor()
        self.detector = AnomalyDetector()
        self.file_service = FileService()
        # AI 설정을 클래스 인스턴스에 저장합니다.
        self.ai_config = get_ai_config()
    
    def run_complete_analysis(
        self,
        file_path: str,
        exclude_columns: Optional[List[str]] = None,
        user_col: Optional[str] = None,
        time_col: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        완전한 이상 탐지 분석을 실행합니다.
        
        Args:
            file_path: 입력 CSV 파일 경로
            exclude_columns: 분석에서 제외할 컬럼
            user_col: 사용자 식별자 컬럼 이름
            time_col: 시간/타임스탬프 컬럼 이름
            
        Returns:
            분석 결과를 담은 딕셔너리
        """
        try:
            # 1단계: 데이터 로드 및 유효성 검사
            print("1단계: 데이터 로딩 중...")
            data = self.file_service.read_csv_file(file_path)
            
            # 사용자 및 시간 컬럼 처리
            user_col, time_col = self._prepare_special_columns(data, user_col, time_col)
            
            # 2단계: 모델링을 위한 데이터 준비 (특성에서 사용자 컬럼 제외)
            print("2단계: 모델링을 위한 데이터 준비 중...")
            model_data = self._prepare_model_data(data, exclude_columns, user_col)
            
            # 3단계: 데이터 전처리
            print("3단계: 데이터 전처리 중...")
            processed_data, categorical_cols, encoder = self.preprocessor.fit_transform(
                model_data, exclude_columns
            )
            
            # 4단계: 모델 학습 및 예측
            print("4단계: 모델 학습 및 이상 탐지 중...")
            predictions, scores = self.detector.fit_predict(processed_data)
            
            # 5단계: 원본 데이터와 결과 결합
            print("5단계: 결과 결합 중...")
            results_df = self._combine_results(data, processed_data, predictions, scores)
            
            # 6단계: 중간 파일 저장
            print("6단계: 중간 파일 저장 중...")
            file_paths = self._save_intermediate_files(
                file_path, processed_data, predictions, scores, encoder
            )
            
            # 7단계: 가독성 있는 결과 복원
            print("7단계: 가독성 있는 결과 생성 중...")
            final_results_path = self._create_readable_results(
                file_paths['full_results'], encoder, file_path
            )
            
            # 8단계: 시각화 생성
            print("8단계: 시각화 생성 중...")
            visualizations = self._generate_visualizations(
                final_results_path, user_col, time_col
            )
            
            # 9단계: 요약 생성
            print("9단계: 분석 요약 생성 중...")
            summary = self._create_analysis_summary(
                results_df, user_col, time_col
            )
            
            # 10단계: 최종 결과 준비
            final_results = self._prepare_final_results(
                results_df, final_results_path, summary, visualizations,
                user_col, time_col
            )
            
            print(f"분석이 성공적으로 완료되었습니다!")
            return final_results
            
        except Exception as e:
            raise AnomalyDetectionError(f"분석 실패: {str(e)}")
    
    def _prepare_special_columns(
        self, 
        data: pd.DataFrame, 
        user_col: Optional[str], 
        time_col: Optional[str]
    ) -> Tuple[str, Optional[str]]:
        """사용자 및 시간 컬럼을 준비합니다."""
        # 사용자 컬럼 처리
        if user_col is None or user_col == "":
            data['user'] = 'all'
            user_col = 'user'
        
        # 시간 컬럼 처리
        if time_col is None or time_col == "":
            time_col = None
        
        return user_col, time_col
    
    def _prepare_model_data(
        self, 
        data: pd.DataFrame, 
        exclude_columns: Optional[List[str]], 
        user_col: str
    ) -> pd.DataFrame:
        """사용자 컬럼을 제외하여 모델링용 데이터를 준비합니다."""
        model_data = data.copy()
        
        # 모델 특성에서 사용자 컬럼 제거
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
        """원본 데이터와 모델 결과를 결합합니다."""
        results = processed_data.copy().reset_index(drop=True)
        results['Anomaly'] = predictions
        results['Anomaly_Score'] = scores
        
        # 이상 점수 기준으로 내림차순 정렬
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
        """SHAP 및 기타 분석을 위한 중간 파일을 저장합니다."""
        base_filename = original_file_path.replace('.csv', '')
        
        # 모델 저장
        model_path = f"{base_filename}_model.pkl"
        self.detector.save_model(model_path)
        
        # SHAP 입력 데이터 저장 (크기 제한)
        # ai_config에서 shap_max_rows 값을 가져옵니다.
        analysis_params = self.ai_config.get("analysis_params", {})
        shap_max_rows = analysis_params.get("shap_max_rows", 100)
        
        shap_input = processed_data.head(shap_max_rows)
        shap_input = shap_input.round(6)  # 공간 절약을 위해 정밀도 감소
        shap_input_path = f"{base_filename}_X_for_shap.csv"
        shap_input.to_csv(shap_input_path, index=False)
        
        # SHAP 값 저장
        shap_values = self.detector.get_feature_importance(processed_data)
        if shap_values is not None:
            shap_values_path = f"{base_filename}_shap_values.npy"
            np.save(shap_values_path, shap_values)
        
        # 전체 결과를 위해 원본 데이터와 결과 결합
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
        """인코딩된 값을 복원하여 사람이 읽을 수 있는 결과를 생성합니다."""
        if encoder is not None:
            readable_path = original_file_path.replace('.csv', '_full_data_with_anomaly_info_readable.csv')
            restore_and_save_readable_anomalies(
                anomaly_csv_path=full_results_path,
                encoder_mapping_dict=encoder.mapping,
                output_path=readable_path
            )
            return readable_path
        else:
            print("사용 가능한 인코더가 없어 복원 단계를 건너뜁니다.")
            return full_results_path
    
    def _generate_visualizations(
        self,
        results_path: str,
        user_col: str,
        time_col: Optional[str]
    ) -> Dict[str, Optional[str]]:
        """시각화 HTML을 생성합니다."""
        try:
            df_full = pd.read_csv(results_path)
            
            # 컬럼 이름 정리 (.1 접미사 제거)
            for col in df_full.columns:
                if col.endswith('.1'):
                    orig_col = col[:-2]
                    if orig_col in df_full.columns:
                        df_full.drop(columns=[orig_col], inplace=True)
                    df_full.rename(columns={col: orig_col}, inplace=True)
            
            # 이상치에 대해서만 시각화 생성
            anomalies_df = df_full[df_full['Anomaly'] == 1]
            
            visualizations = {}
            
            # 점수 분포
            visualizations['score_distribution'] = plot_anomaly_score_distribution(
                df_full, threshold=config.ui.default_threshold, score_col='Anomaly_Score'
            )
            
            # 사용자 기반 시각화
            visualizations['user_graph'] = plot_anomaly_by_user(
                anomalies_df, user_col=user_col, for_dashboard=True
            )
            
            # 시간 기반 시각화 (시간 컬럼이 있는 경우)
            if time_col is not None and time_col in df_full.columns:
                visualizations['hour_graph'] = plot_anomaly_by_hour(
                    anomalies_df, user_col=user_col, time_col=time_col
                )
            else:
                visualizations['hour_graph'] = None
                print("시간 컬럼을 사용할 수 없어 시간 기반 시각화를 건너뜁니다.")
            
            return visualizations
            
        except Exception as e:
            print(f"시각화 생성 실패: {e}")
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
        """분석 요약 및 설명을 생성합니다."""
        from ..ai_script import generate_description  # 순환 참조 방지를 위해 여기서 임포트
        
        total_count = len(results_df)
        anomaly_count = int(results_df['Anomaly'].sum())
        
        # 설명 HTML 생성
        anomalies_only = results_df[results_df['Anomaly'] == 1] if anomaly_count > 0 else pd.DataFrame()
        
        if not anomalies_only.empty:
            description_html = generate_description(anomalies_only, user_col, time_col)
        else:
            description_html = "<div>데이터셋에서 이상치가 탐지되지 않았습니다.</div>"
        
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
        """최종 결과 딕셔너리를 준비합니다."""
        # 출력을 위해 최종 결과 로드
        df_full = pd.read_csv(final_results_path)
        
        # 이상치 추출 및 프론트엔드용 데이터 준비
        detected_anomalies = df_full[df_full['Anomaly'] == 1]
        
        # 표시에 불필요한 TF-IDF 컬럼 제거
        tfidf_cols = [col for col in detected_anomalies.columns if '_tfidf_' in col]
        detected_for_display = detected_anomalies.drop(columns=tfidf_cols, errors='ignore')
        
        # ai_config에서 max_preview_rows 값을 가져옵니다.
        analysis_params = self.ai_config.get("analysis_params", {})
        max_preview_rows = analysis_params.get("max_preview_rows", 100)
        
        # 미리보기를 위한 상위 결과 가져오기
        preview_top100 = detected_for_display.sort_values(
            by="Anomaly_Score", ascending=False
        ).head(max_preview_rows)
        
        # 테이블 HTML 준비
        if len(preview_top100) > 0:
            table_html = preview_top100.to_html(index=False, classes="table table-sm")
        else:
            table_html = "<p>이상치가 없습니다.</p>"
        
        # JSON 직렬화를 위한 데이터 정리
        def clean_for_json(obj):
            """JSON 직렬화를 위해 데이터를 정리합니다."""
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
        
        # 다운로드용 레코드 준비
        anomaly_records = clean_for_json(
            detected_for_display.head(max_preview_rows).to_dict(orient="records")
        )
        all_records = clean_for_json(
            df_full.drop(columns=tfidf_cols, errors='ignore').head(max_preview_rows).to_dict(orient="records")
        )
        
        # 탐지된 이상치 별도 저장
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
    하위 호환성을 위한 레거시 함수입니다.
    
    이 함수는 새로운 모듈식 접근 방식을 사용하면서 기존 API를 유지합니다.
    
    Args:
        file_path: 입력 CSV 파일 경로
        exclude_columns: 분석에서 제외할 컬럼
        user_col: 사용자 식별자 컬럼 이름
        time_col: 시간/타임스탬프 컬럼 이름
        
    Returns:
        분석 결과를 담은 딕셔너리
    """
    service = AnalysisService()
    return service.run_complete_analysis(file_path, exclude_columns, user_col, time_col)