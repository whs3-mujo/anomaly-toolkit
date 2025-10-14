"""
웹 뷰 관련 서비스 모듈
"""

import os
import json
import uuid
import pandas as pd
import numpy as np
import threading
import time
from typing import Dict, Any, Optional, List, Tuple
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.utils import timezone

from ..models import AnalysisSession
from ..ai_script import detect_anomalies
from ..visualize_graph import plot_anomaly_by_hour


class ViewService:
    """웹 뷰 관련 서비스를 담당하는 클래스"""
    
    @staticmethod
    def save_uploaded_file(file) -> str:
        """업로드된 파일을 저장하고 경로를 반환합니다."""
        upload_dir = os.path.join(settings.MEDIA_ROOT, "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, file.name)
        with open(file_path, "wb+") as destination:
            for chunk in file.chunks():
                destination.write(chunk)
        return file_path
    
    @staticmethod
    def create_analysis_session(filename: str, file_path: str, file_type: str, 
                              analysis_result: Dict[str, Any]) -> AnalysisSession:
        """새로운 분석 세션을 생성합니다."""
        session_id = str(uuid.uuid4())
        return AnalysisSession.objects.create(
            session_id=session_id,
            original_filename=filename,
            file_path=file_path,
            file_type=file_type,
            analysis_result=analysis_result
        )
    
    @staticmethod
    def process_anomaly_detection(file, exclude_columns_str: str, user_col: str, 
                                time_col: str, q_value: str) -> Dict[str, Any]:
        """이상치 탐지 처리를 위한 메인 로직"""
        
        # 매개변수 전처리
        exclude_columns = [col.strip() for col in exclude_columns_str.split(",") if col.strip()]
        
        # q값 처리
        try:
            q = float(q_value)
            q = max(0.01, min(0.5, q))  # 1%~50% 범위 제한
        except (ValueError, TypeError):
            q = 0.05
        
        # 빈 문자열을 None으로 변환
        user_col = user_col if user_col else None
        time_col = time_col if time_col else None
        
        # 파일 저장
        file_path = ViewService.save_uploaded_file(file)
        
        # 타임아웃 설정 (10분)
        timeout = 600
        result = None
        analysis_error = False
        
        def run_analysis():
            nonlocal result, analysis_error
            try:
                result = detect_anomalies(
                    file_path, exclude_columns, 
                    user_col=user_col, time_col=time_col, q=q
                )
            except Exception as e:
                analysis_error = True
                print(f"분석 중 오류 발생: {e}")
        
        # 분석 스레드 시작
        analysis_thread = threading.Thread(target=run_analysis)
        analysis_thread.start()
        analysis_thread.join(timeout)
        
        # 타임아웃 또는 오류 체크
        if analysis_thread.is_alive() or analysis_error or result is None:
            raise Exception('처리할 수 없는 데이터셋입니다. 10분 이상 소요되었거나 분석 중 오류가 발생했습니다.')
        
        # 시간별 그래프 HTML 생성
        result_csv_path = result.get("result_csv_path")
        df_result = pd.read_csv(result_csv_path)
        
        user_graph_html = result.get('user_graph_html')
        score_graph_html = result.get('score_distribution_html')
        
        if user_col and time_col and user_col in df_result.columns and time_col in df_result.columns:
            hour_graph_html_top3 = plot_anomaly_by_hour(df_result, user_col, time_col, top_n=3)
            hour_graph_html_top10 = plot_anomaly_by_hour(df_result, user_col, time_col, top_n=10)
        else:
            hour_graph_html_top3 = None
            hour_graph_html_top10 = None
        
        # 분석 세션 생성
        AnalysisSession.objects.create(
            session_id=str(uuid.uuid4()),
            original_filename=file.name,
            file_path=file_path,
            file_type=os.path.splitext(file.name)[-1][1:].upper(),
            analysis_result=result,
            user_col=user_col,
            time_col=time_col,
            user_graph_html=user_graph_html,
            hour_graph_html_top3=hour_graph_html_top3,
            hour_graph_html_top10=hour_graph_html_top10,
            score_graph_html=score_graph_html,
        )
        
        return result


class FilePreviewService:
    """파일 미리보기 관련 서비스"""
    
    @staticmethod
    def preview_csv_columns(uploaded_file) -> Dict[str, Any]:
        """CSV 파일의 컬럼과 미리보기 데이터를 반환합니다."""
        
        # 파일 크기 체크 (100MB 제한)
        if uploaded_file.size > 100 * 1024 * 1024:
            raise ValueError("파일이 너무 큽니다. 100MB 이하의 파일만 업로드 가능합니다.")
        
        df = None
        
        # 여러 인코딩 시도
        for encoding in ["utf-8", "cp949", "euc-kr", "latin1"]:
            try:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, nrows=5, encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
            except Exception:
                continue
        else:
            raise ValueError("지원하지 않는 파일 인코딩입니다. UTF-8, CP949, EUC-KR, Latin1 인코딩을 지원합니다.")
        
        if df is None or df.empty:
            raise ValueError("파일이 비어있거나 읽을 수 있는 데이터가 없습니다.")
        
        # 컬럼 수 제한
        if len(df.columns) > 100:
            raise ValueError(f"컬럼이 너무 많습니다 ({len(df.columns)}개). 최대 100개 컬럼까지 지원합니다.")
        
        # 컬럼명 정제
        original_columns = list(df.columns)
        cleaned_columns = []
        
        for col in original_columns:
            if pd.isna(col) or str(col).strip() == '':
                cleaned_columns.append(f"Column_{len(cleaned_columns)}")
            else:
                clean_col = str(col).strip()
                cleaned_columns.append(clean_col)
        
        df.columns = cleaned_columns
        
        # 데이터 품질 체크
        total_cells = df.shape[0] * df.shape[1]
        null_cells = df.isnull().sum().sum()
        null_ratio = null_cells / total_cells if total_cells > 0 else 0
        
        quality_warnings = []
        if null_ratio > 0.8:
            quality_warnings.append(f"데이터의 {null_ratio:.1%}가 결측치입니다.")
        
        # 빈 컬럼 체크
        empty_columns = [col for col in df.columns if df[col].isnull().all()]
        if empty_columns:
            quality_warnings.append(f"빈 컬럼이 {len(empty_columns)}개 있습니다: {', '.join(empty_columns[:5])}")
        
        # 미리보기 데이터 생성
        preview_df = df.head(2)
        preview_dict = []
        
        for _, row in preview_df.iterrows():
            row_dict = {}
            for col in df.columns:
                value = row[col]
                if pd.isna(value):
                    row_dict[col] = ""
                else:
                    str_value = str(value)
                    if len(str_value) > 50:
                        row_dict[col] = str_value[:47] + "..."
                    else:
                        row_dict[col] = str_value
            preview_dict.append(row_dict)
        
        response_data = {
            "columns": cleaned_columns,
            "preview": preview_dict,
            "total_columns": len(cleaned_columns),
            "sample_rows": len(preview_df)
        }
        
        if quality_warnings:
            response_data["warnings"] = quality_warnings
        
        return response_data