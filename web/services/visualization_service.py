"""
시각화 관련 서비스 모듈

이 모듈은 ai_script.py에서 사용하는 그래프 생성과 관련된
모든 시각화 기능을 제공합니다.
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any
import warnings

# visualize_graph 모듈에서 그래프 함수들 import
from ..visualize_graph import (
    plot_anomaly_by_hour,
    plot_anomaly_by_user, 
    plot_anomaly_score_distribution
)


class VisualizationService:
    """시각화 관련 기능을 담당하는 서비스 클래스"""
    
    @staticmethod
    def generate_all_graphs(df_full: pd.DataFrame, user_col: str, time_col: Optional[str] = None, 
                          score_col: str = 'Anomaly_Score', threshold: float = -0.20) -> Dict[str, Optional[str]]:
        """
        모든 그래프를 생성합니다.
        
        Args:
            df_full: 전체 결과 데이터프레임
            user_col: 사용자 컬럼명
            time_col: 시간 컬럼명 (선택사항)
            score_col: 이상치 점수 컬럼명
            threshold: 점수 분포 그래프 임계값
            
        Returns:
            생성된 그래프 HTML들의 딕셔너리
        """
        result = {
            'score_distribution_html': None,
            'user_graph_html': None,
            'hour_graph_html': None
        }
        
        try:
            print("그래프 생성 시작...")
            
            # 1. 이상치 점수 분포 그래프
            try:
                result['score_distribution_html'] = plot_anomaly_score_distribution(
                    df_full, threshold=threshold, score_col=score_col
                )
                print("이상치 점수 분포 그래프 생성 완료")
            except Exception as e:
                print(f"점수 분포 그래프 생성 중 오류: {e}")
            
            # 2. 사용자별 그래프 (이상치만)
            try:
                anomaly_data = df_full[df_full['Anomaly'] == 1]
                if not anomaly_data.empty:
                    print(f"사용자별 그래프 생성 시작... user_col={user_col}")
                    result['user_graph_html'] = plot_anomaly_by_user(
                        anomaly_data, user_col=user_col, top_n=5, for_dashboard=True
                    )
                    print(f"사용자별 그래프 생성 완료, 길이: {len(result['user_graph_html']) if result['user_graph_html'] else 0}")
                else:
                    print("이상치가 없어 사용자별 그래프를 생략합니다.")
            except Exception as e:
                print(f"사용자별 그래프 생성 중 오류: {e}")
            
            # 3. 시간대별 그래프 (시간 컬럼이 있는 경우에만)
            if time_col is not None:
                try:
                    anomaly_data = df_full[df_full['Anomaly'] == 1]
                    if not anomaly_data.empty:
                        result['hour_graph_html'] = plot_anomaly_by_hour(
                            anomaly_data, user_col=user_col, time_col=time_col
                        )
                        print("시간대별 그래프 생성 완료")
                    else:
                        print("이상치가 없어 시간대별 그래프를 생략합니다.")
                except Exception as e:
                    print(f"시간대별 그래프 생성 중 오류: {e}")
            else:
                print("시간 컬럼이 없어 시간대별 그래프를 생략합니다.")
                
        except Exception as e:
            print(f"그래프 시각화 중 전체 오류: {e}")
            import traceback
            traceback.print_exc()
        
        return result
    
    @staticmethod  
    def generate_score_distribution_graph(df: pd.DataFrame, threshold: float = -0.20, 
                                        score_col: str = 'Anomaly_Score') -> Optional[str]:
        """
        이상치 점수 분포 그래프를 생성합니다.
        
        Args:
            df: 데이터프레임
            threshold: 임계값
            score_col: 점수 컬럼명
            
        Returns:
            그래프 HTML 문자열 또는 None
        """
        try:
            return plot_anomaly_score_distribution(df, threshold=threshold, score_col=score_col)
        except Exception as e:
            print(f"점수 분포 그래프 생성 오류: {e}")
            return None
    
    @staticmethod
    def generate_user_graph(df: pd.DataFrame, user_col: str, top_n: int = 5, 
                          for_dashboard: bool = True) -> Optional[str]:
        """
        사용자별 이상치 그래프를 생성합니다.
        
        Args:
            df: 이상치 데이터프레임
            user_col: 사용자 컬럼명
            top_n: 상위 n명 표시
            for_dashboard: 대시보드용 여부
            
        Returns:
            그래프 HTML 문자열 또는 None
        """
        try:
            return plot_anomaly_by_user(df, user_col=user_col, top_n=top_n, for_dashboard=for_dashboard)
        except Exception as e:
            print(f"사용자별 그래프 생성 오류: {e}")
            return None
    
    @staticmethod
    def generate_hour_graph(df: pd.DataFrame, user_col: str, time_col: str) -> Optional[str]:
        """
        시간대별 이상치 그래프를 생성합니다.
        
        Args:
            df: 이상치 데이터프레임
            user_col: 사용자 컬럼명
            time_col: 시간 컬럼명
            
        Returns:
            그래프 HTML 문자열 또는 None
        """
        try:
            return plot_anomaly_by_hour(df, user_col=user_col, time_col=time_col)
        except Exception as e:
            print(f"시간대별 그래프 생성 오류: {e}")
            return None