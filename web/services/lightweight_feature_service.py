"""
경량화된 특성 중요도 서비스 (SHAP 제거)

이 모듈은 SHAP 없이 간단한 특성 중요도 분석을 제공합니다.
"""

import numpy as np
import pandas as pd
from typing import Optional, Any, List, Tuple, Dict
import matplotlib.pyplot as plt
import matplotlib
from io import BytesIO
import base64

from ..models import AnalysisSession


class LightweightFeatureService:
    """경량화된 특성 중요도 분석 서비스"""
    
    @staticmethod
    def generate_feature_importance_plot(session: AnalysisSession, row_index: int) -> Dict[str, Any]:
        """특성 중요도 플롯을 생성합니다 (SHAP 대신 간단한 분석)."""
        
        try:
            # 원본 데이터 로드
            original_df = pd.read_csv(session.file_path)
            
            # 해당 행의 데이터 추출
            if row_index >= len(original_df):
                return {
                    'success': False,
                    'error': '잘못된 행 인덱스입니다.'
                }
            
            target_row = original_df.iloc[row_index]
            
            # 숫자형 컬럼들의 이상 정도 계산
            numeric_cols = original_df.select_dtypes(include=[np.number]).columns
            feature_importance = []
            
            for col in numeric_cols:
                if col in ['Anomaly', 'Anomaly_Score']:
                    continue
                    
                col_mean = original_df[col].mean()
                col_std = original_df[col].std()
                
                if col_std > 0:
                    # Z-score 기반 이상 정도 계산
                    z_score = abs((target_row[col] - col_mean) / col_std)
                    feature_importance.append({
                        'feature': col,
                        'importance': z_score,
                        'value': target_row[col]
                    })
            
            # 카테고리형 컬럼들의 희귀도 계산
            categorical_cols = original_df.select_dtypes(include=['object']).columns
            
            for col in categorical_cols:
                value_counts = original_df[col].value_counts()
                total_count = len(original_df)
                
                # 희귀도 계산 (1 - frequency)
                frequency = value_counts.get(target_row[col], 0) / total_count
                rarity = 1 - frequency
                
                feature_importance.append({
                    'feature': col,
                    'importance': rarity * 2,  # 스케일 조정
                    'value': target_row[col]
                })
            
            # 중요도 순으로 정렬
            feature_importance.sort(key=lambda x: x['importance'], reverse=True)
            
            # 상위 6개만 선택
            top_features = feature_importance[:6]
            
            # 빈 항목으로 채우기
            while len(top_features) < 6:
                top_features.append({
                    'feature': '',
                    'importance': 0,
                    'value': ''
                })
            
            # 시각화 생성
            plot_html = LightweightFeatureService._create_importance_visualization(top_features, row_index)
            
            # 설명 테이블 생성
            explanation_html = LightweightFeatureService._generate_importance_table(top_features)
            
            middle_html = """
            <div style='margin: 1rem 0; color: #666; font-size: 1.05rem; line-height: 1.5;'>
                이 그래프는 해당 로그에서 일반적이지 않은 특성들을 중요도 순으로 보여줍니다.
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
            
        except Exception as e:
            return {
                'success': False,
                'error': f'특성 중요도 분석 중 오류: {str(e)}'
            }
    
    @staticmethod
    def _create_importance_visualization(features: List[Dict], row_index: int) -> str:
        """특성 중요도 시각화를 생성합니다."""
        max_len = 6
        y_pos = np.arange(max_len)
        
        fig, ax = plt.subplots(figsize=(10, 8))
        
        # 중요도 값 추출
        importance_values = [f['importance'] for f in features]
        max_value = max(importance_values) if importance_values else 1
        
        if max_value > 0:
            ax.set_xlim(0, max_value * 1.2)
        else:
            ax.set_xlim(0, 1)
        
        ax.barh(y_pos, importance_values, color='lightcoral', label='특성 중요도', 
               align='center', height=0.6)
        ax.axvline(x=0, color='black', linewidth=1)
        
        ax.grid(axis='y', visible=False)
        ax.grid(axis='x', visible=True, linestyle='--', alpha=0.7)
        
        ax.set_yticks(y_pos)
        ax.set_yticklabels([''] * max_len)
        ax.invert_yaxis()
        
        # 레이블 추가
        for i, feature in enumerate(features):
            if feature['feature'] and feature['importance'] > 0:
                text_x = feature['importance'] + (max_value * 0.01) if max_value > 0 else 0.01
                if text_x > max_value * 1.15:
                    text_x = max_value * 1.15
                    ha = 'right'
                else:
                    ha = 'left'
                
                ax.text(text_x, i, feature['feature'], ha=ha, va='center',
                       fontsize=9, fontweight='bold',
                       bbox=dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.8))
        
        ax.set_title(f"{row_index+1}번 ROW - 특성 중요도", fontweight='bold', fontsize=11, pad=10)
        ax.set_xlabel("중요도 (표준화된 이상 정도)", fontsize=10)
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
    def _generate_importance_table(features: List[Dict]) -> str:
        """특성 중요도 설명 테이블을 생성합니다."""
        table_html = """
        <div style="margin-top: 1rem;">
            <h4 style="color: #1976d2; font-size: 1.25rem; font-weight: 700; margin-bottom: 1rem; border-bottom: 2px solid #e3f2fd; padding-bottom: 0.5rem;">상세 설명</h4>
            <table style="width: 100%; border-collapse: collapse; border: 1px solid #dee2e6;">
                <thead>
                    <tr style="background: #f1f3f5;">
                        <th style="padding: 12px 15px; text-align: left; font-weight: 600; color: #495057; border: 1px solid #dee2e6;">특성</th>
                        <th style="padding: 12px 15px; text-align: center; font-weight: 600; color: #495057; border: 1px solid #dee2e6;">값</th>
                        <th style="padding: 12px 15px; text-align: center; font-weight: 600; color: #495057; border: 1px solid #dee2e6;">중요도</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for feature in features[:6]:
            if not feature['feature']:
                continue
            
            importance = feature['importance']
            
            if importance > 2.0:
                color = "#c62828"
                bg_color = "#ffebee"
                level = "매우 높음"
            elif importance > 1.5:
                color = "#ef6c00"
                bg_color = "#fff3e0"
                level = "높음"
            elif importance > 1.0:
                color = "#f57f17"
                bg_color = "#fffde7"
                level = "중간"
            elif importance > 0.5:
                color = "#1976d2"
                bg_color = "#e3f2fd"
                level = "낮음"
            else:
                color = "#388e3c"
                bg_color = "#e8f5e8"
                level = "매우 낮음"
            
            # 값 표시 (너무 길면 자르기)
            value_str = str(feature['value'])
            if len(value_str) > 20:
                value_str = value_str[:17] + "..."
            
            table_html += f"""
            <tr style="background: white;">
                <td style="padding: 10px 15px; border: 1px solid #dee2e6; font-weight: 500; color: #333;">{feature['feature']}</td>
                <td style="padding: 10px 15px; border: 1px solid #dee2e6; text-align: center; font-family: monospace; font-size: 0.9em;">{value_str}</td>
                <td style="padding: 10px 15px; border: 1px solid #dee2e6; text-align: center; background: {bg_color}; color: {color}; font-weight: bold; font-size: 1.1rem;">
                    {level}<br><small style="font-size: 0.9em; color: #666;">({importance:.2f})</small>
                </td>
            </tr>
            """
        
        table_html += """
                </tbody>
            </table>
            <div style="margin-top: 10px; font-size: 0.95em; color: #666; line-height: 1.5;">
                <strong>중요도 범례:</strong> 
                <span style="color: #c62828; font-weight: bold;">매우 높음(2.0↑)</span> | 
                <span style="color: #ef6c00; font-weight: bold;">높음(1.5~2.0)</span> | 
                <span style="color: #f57f17; font-weight: bold;">중간(1.0~1.5)</span> | 
                <span style="color: #1976d2; font-weight: bold;">낮음(0.5~1.0)</span> | 
                <span style="color: #388e3c; font-weight: bold;">매우 낮음(0.5↓)</span>
                <br><small>* 중요도는 통계적 이상 정도와 데이터 희귀성을 기반으로 계산됩니다.</small>
            </div>
        </div>
        """
        
        return table_html