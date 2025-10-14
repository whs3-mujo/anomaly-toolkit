"""
SHAP 관련 분석 서비스

이 모듈은 SHAP 값 계산 및 시각화 관련 기능을 담당합니다.
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from io import BytesIO
import base64
from typing import Dict, Any, Optional

from ..models import AnalysisSession


class ShapService:
    """SHAP 분석 관련 서비스"""
    
    @staticmethod
    def generate_shap_plot(session: AnalysisSession, row_index: int) -> Dict[str, Any]:
        """특정 행에 대한 SHAP 플롯을 생성합니다."""
        
        # 원본 데이터 로드
        try:
            original_df = pd.read_csv(session.file_path)
            original_columns = set(original_df.columns)
        except (FileNotFoundError, pd.errors.EmptyDataError, pd.errors.ParserError):
            original_df = None
            original_columns = set()
        
        # SHAP 데이터 로드
        X = pd.read_csv(session.file_path.replace(".csv", "_X_for_shap.csv"))
        shap_values = np.load(session.file_path.replace(".csv", "_shap_values.npy"))
        feature_cols = X.columns.tolist()
        
        # SHAP 값 추출 및 정합성 확인
        row = ShapService._extract_shap_row(shap_values, row_index)
        
        # 길이 정합성 강제
        min_len = min(len(feature_cols), len(row), X.shape[1])
        feature_cols = feature_cols[:min_len]
        row = row[:min_len]
        X = X.iloc[:, :min_len]
        
        # SHAP DataFrame 생성
        shap_df = pd.DataFrame({
            'feature': feature_cols,
            'shap_value': row,
            'abs_val': np.abs(row),
            'data': X.iloc[row_index].values
        })
        
        # TF-IDF 컬럼 처리
        merged_shap_df = ShapService._merge_tfidf_features(
            shap_df, original_df, original_columns, row_index
        )
        
        # 음수 SHAP 값만 필터링하여 상위 6개 선택
        negative_df = merged_shap_df[merged_shap_df['shap_value'] < 0].sort_values(
            by='abs_val', ascending=False
        ).reset_index(drop=True)
        negative_df = negative_df.reindex(range(6)).fillna({
            'feature': '', 'shap_value': 0, 'abs_val': 0, 'data': 0
        })
        
        # 시각화 생성
        plot_html = ShapService._create_shap_visualization(negative_df, row_index)
        
        # 설명 테이블 생성
        explanation_html = ShapService._generate_shap_table(negative_df)
        
        middle_html = """
        <div style='margin: 1rem 0; color: #666; font-size: 1.05rem; line-height: 1.5;'>
            이 그래프는 AI가 해당 로그를 이상으로 판단하는 데 영향을 준 항목들을 기여도 순으로 보여줍니다.
        </div>
        """
        
        description_html = ""
        if hasattr(session, 'analysis_result') and session.analysis_result:
            description_html = session.analysis_result.get('text_html', '')
        
        return {
            'success': True,
            'plot_html': plot_html,
            'shap_middle_html': middle_html,
            'shap_explanation': explanation_html,
            'description_html': description_html
        }
    
    @staticmethod
    def _extract_shap_row(shap_values: np.ndarray, row_index: int) -> np.ndarray:
        """SHAP 값 배열에서 특정 행을 안전하게 추출합니다."""
        if isinstance(shap_values, np.ndarray) and shap_values.dtype != object:
            if shap_values.ndim == 2:
                row = shap_values[int(row_index)]
            elif shap_values.ndim == 3:
                row = shap_values[0, int(row_index), :]  # 첫 클래스 사용
            else:
                row = np.atleast_1d(shap_values[int(row_index)])
        else:
            # object array 또는 list 처리
            shap_list = shap_values.tolist() if isinstance(shap_values, np.ndarray) else shap_values
            if isinstance(shap_list, list):
                if len(shap_list) > 0 and isinstance(shap_list[0], (np.ndarray, list)):
                    first = np.asarray(shap_list[0])
                    if first.ndim == 2:
                        row = np.asarray(shap_list[0][int(row_index)])
                    elif first.ndim == 3:
                        row = np.asarray(shap_list[0][0, int(row_index), :])
                    else:
                        row = np.asarray(shap_list[0]).reshape(-1)
                else:
                    row = np.asarray(shap_list[int(row_index)]).reshape(-1)
            else:
                row = np.asarray(shap_list).reshape(-1)
        
        return np.asarray(row).ravel()
    
    @staticmethod
    def _merge_tfidf_features(shap_df: pd.DataFrame, original_df: Optional[pd.DataFrame], 
                            original_columns: set, row_index: int) -> pd.DataFrame:
        """TF-IDF 피처를 원본 컬럼으로 통합합니다."""
        feature_cols = shap_df['feature'].tolist()
        
        # TF-IDF 컬럼 식별 및 매핑
        tfidf_cols = [col for col in feature_cols if '_tfidf_' in col]
        tfidf_mappings = {}
        lower_original_columns = {col.lower() for col in original_columns}
        
        for col in tfidf_cols:
            source_col = col.split('_tfidf_')[0]
            if source_col.lower() in lower_original_columns:
                matched_col = [col for col in original_columns if col.lower() == source_col.lower()][0]
                display_name = f"{matched_col}"
            else:
                display_name = f"added({source_col})"
            
            if display_name not in tfidf_mappings:
                tfidf_mappings[display_name] = []
            tfidf_mappings[display_name].append(col)
        
        merged_shap_df = []
        
        # TF-IDF 피처 통합
        for source_col, related_tfidf in tfidf_mappings.items():
            tfidf_rows = shap_df[shap_df['feature'].isin(related_tfidf)]
            total_shap = tfidf_rows['shap_value'].sum()
            
            # 데이터 값 계산
            if original_df is not None and source_col in original_df.columns:
                original_value = str(original_df[source_col].iloc[row_index])
                unique_values = original_df[source_col].nunique()
                current_frequency = (original_df[source_col] == original_value).sum()
                data_value = 1 - (current_frequency / len(original_df))
            else:
                if not tfidf_rows.empty:
                    data_value = np.average(tfidf_rows['data'], weights=tfidf_rows['abs_val'])
                else:
                    data_value = 0
            
            merged_shap_df.append({
                'feature': f"{source_col}",
                'shap_value': total_shap,
                'abs_val': abs(total_shap),
                'data': data_value
            })
        
        # 나머지 non-TF-IDF 피처 추가
        all_tfidf_features = [item for sublist in tfidf_mappings.values() for item in sublist]
        non_tfidf_features = [f for f in feature_cols if f not in all_tfidf_features]
        
        for feature in non_tfidf_features:
            idx = feature_cols.index(feature)
            
            if original_df is not None and feature in original_df.columns:
                original_value = original_df[feature].iloc[row_index]
                if pd.api.types.is_numeric_dtype(original_df[feature]):
                    mean_value = original_df[feature].mean()
                    data_value = abs(original_value - mean_value)
                else:
                    data_value = abs(shap_df[shap_df['feature'] == feature]['data'].iloc[0])
            else:
                data_value = abs(shap_df[shap_df['feature'] == feature]['data'].iloc[0])
            
            merged_shap_df.append({
                'feature': feature,
                'shap_value': shap_df[shap_df['feature'] == feature]['shap_value'].iloc[0],
                'abs_val': abs(shap_df[shap_df['feature'] == feature]['shap_value'].iloc[0]),
                'data': data_value
            })
        
        return pd.DataFrame(merged_shap_df)
    
    @staticmethod
    def _create_shap_visualization(negative_df: pd.DataFrame, row_index: int) -> str:
        """SHAP 시각화를 생성합니다."""
        max_len = 6
        y_pos = np.arange(max_len)
        
        fig, ax = plt.subplots(figsize=(10, 8))
        flipped_values = -negative_df['shap_value']
        max_value = flipped_values.max()
        
        if max_value > 0:
            ax.set_xlim(0, max_value * 1.2)
        else:
            ax.set_xlim(0, 1)
        
        ax.barh(y_pos, flipped_values, color='salmon', label='이상치 기여도', 
               align='center', height=0.6)
        ax.axvline(x=0, color='black', linewidth=1)
        
        ax.grid(axis='y', visible=False)
        ax.grid(axis='x', visible=True, linestyle='--', alpha=0.7)
        
        ax.set_yticks(y_pos)
        ax.set_yticklabels([''] * max_len)
        ax.invert_yaxis()
        
        # 레이블 추가
        for i, (label, value) in enumerate(zip(negative_df['feature'], flipped_values)):
            if label and value > 0:
                text_x = value + (max_value * 0.01) if max_value > 0 else 0.01
                if text_x > max_value * 1.15:
                    text_x = max_value * 1.15
                    ha = 'right'
                else:
                    ha = 'left'
                
                ax.text(text_x, i, label, ha=ha, va='center',
                       fontsize=9, fontweight='bold',
                       bbox=dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.8))
        
        ax.set_title(f"{row_index+1}번 ROW", fontweight='bold', fontsize=11, pad=10)
        ax.set_xlabel("영향도 크기 (SHAP)", fontsize=10)
        ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), frameon=False, fontsize=9)
        
        plt.tight_layout()
        plt.subplots_adjust(left=0.02, right=0.98, top=0.85, bottom=0.20)
        
        # 이미지를 base64로 인코딩
        buffer = BytesIO()
        fig.savefig(buffer, format="png", dpi=100, bbox_inches='tight')
        buffer.seek(0)
        image_png = buffer.getvalue()
        buffer.close()
        plt.close(fig)
        
        encoded = base64.b64encode(image_png).decode('utf-8')
        return f'''
        <div style="width: 100%; height: 100%; overflow-y: auto; overflow-x: hidden;">
            <img src="data:image/png;base64,{encoded}" style="width:100%; max-width:100%; height:auto;">
        </div>
        '''
    
    @staticmethod
    def _generate_shap_table(shap_df: pd.DataFrame) -> str:
        """SHAP 설명 테이블을 생성합니다."""
        table_html = """
        <div style="margin-top: 1rem;">
            <h4 style="color: #1976d2; font-size: 1.25rem; font-weight: 700; margin-bottom: 1rem; border-bottom: 2px solid #e3f2fd; padding-bottom: 0.5rem;">상세 설명</h4>
            <table style="width: 100%; border-collapse: collapse; border: 1px solid #dee2e6;">
                <thead>
                    <tr style="background: #f1f3f5;">
                        <th style="padding: 12px 15px; text-align: left; font-weight: 600; color: #495057; border: 1px solid #dee2e6;">컬럼</th>
                        <th style="padding: 12px 15px; text-align: center; font-weight: 600; color: #495057; border: 1px solid #dee2e6;">기여도</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for idx, row in shap_df.head(6).iterrows():
            feature = row['feature']
            if not feature:
                continue
            
            shap_value = abs(row['shap_value'])
            
            if shap_value > 0.1:
                color = "#c62828"
                bg_color = "#ffebee"
                level = "높음"
            elif shap_value > 0.05:
                color = "#ef6c00"
                bg_color = "#fff3e0"
                level = "중간"
            elif shap_value > 0.01:
                color = "#f57f17"
                bg_color = "#fffde7"
                level = "약간"
            else:
                color = "#1565c0"
                bg_color = "#e3f2fd"
                level = "미미"
            
            table_html += f"""
            <tr style="background: white;">
                <td style="padding: 10px 15px; border: 1px solid #dee2e6; font-weight: 500; color: #333;">{feature}</td>
                <td style="padding: 10px 15px; border: 1px solid #dee2e6; text-align: center; background: {bg_color}; color: {color}; font-weight: bold; font-size: 1.1rem;">
                    {level}<br><small style="font-size: 0.9em; color: #666;">({shap_value:.3f})</small>
                </td>
            </tr>
            """
        
        table_html += """
                </tbody>
            </table>
            <div style="margin-top: 10px; font-size: 0.95em; color: #666; line-height: 1.5;">
                <strong><br>기여도 범례</br></strong> 
                <span style="color: #c62828; font-weight: bold;">높음(0.1↑)</span> | 
                <span style="color: #ef6c00; font-weight: bold;">중간(0.05~0.1)</span> | 
                <br>
                <span style="color: #f57f17; font-weight: bold;">약간(0.01~0.05)</span> | 
                <span style="color: #1565c0; font-weight: bold;">미미(0.01↓)</span>
            </div>
        </div>
        """
        
        return table_html