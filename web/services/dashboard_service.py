"""
대시보드 및 통계 관련 서비스

이 모듈은 대시보드에서 사용되는 통계 데이터 및 요약 정보 생성을 담당합니다.
"""

import os
import pandas as pd
from typing import Dict, Any, List, Tuple, Optional
from collections import Counter

from ..models import AnalysisSession


class DashboardService:
    """대시보드 관련 서비스"""
    
    @staticmethod
    def get_analysis_history() -> List[Dict[str, Any]]:
        """분석 히스토리 목록을 반환합니다."""
        sessions = AnalysisSession.objects.all().order_by('-created_at')
        history_data = []
        
        for session in sessions:
            history_data.append({
                'id': session.id,
                'session_id': session.session_id,
                'filename': session.get_short_filename(),
                'full_filename': session.original_filename,
                'file_type': session.file_type,
                'created_at': session.created_at.strftime('%Y-%m-%dT%H:%M:%SZ'),
            })
        
        return history_data
    
    @staticmethod
    def get_analysis_detail(session_id: str) -> Dict[str, Any]:
        """특정 분석 결과 상세 정보를 반환합니다."""
        # generate_description을 다른 곳에서 가져와서 사용
        # 순환 참조 방지를 위해 지연 임포트
        
        session = AnalysisSession.objects.get(session_id=session_id)
        
        analysis_result = session.analysis_result.copy() if session.analysis_result else {}
        analysis_result['text_html'] = DashboardService.generate_interactive_summary_html(session)
        
        return {
            'session': {
                'id': session.id,
                'session_id': session.session_id,
                'filename': session.original_filename,
                'file_type': session.file_type,
                'created_at': session.created_at.strftime('%Y-%m-%dT%H:%M:%SZ'),
                'analysis_result': analysis_result,
                'user_graph_html': getattr(session, 'user_graph_html', None),
                'hour_graph_html': getattr(session, 'hour_graph_html_top3', None),
                'score_graph_html': getattr(session, 'score_graph_html', None),
            }
        }
    
    @staticmethod
    def generate_interactive_summary_html(session: AnalysisSession) -> str:
        """분석 결과를 기반으로 인터랙티브 요약 HTML을 생성합니다."""
        if not session.analysis_result:
            return "<p>분석 결과가 없습니다.</p>"
        
        try:
            time_periods, top_users = DashboardService._parse_analysis_data(session)
            
            max_time_period = max(time_periods, key=lambda x: x['count']) if time_periods else None
            max_user = max(top_users, key=lambda x: x['count']) if top_users else None
            
            total_time_anomalies = sum(p['count'] for p in time_periods)
            total_user_anomalies = sum(u['count'] for u in top_users)
            
            # 시간대별 세그먼트 생성
            time_segments = []
            if total_time_anomalies > 0:
                cumulative = 0
                for period in time_periods:
                    percentage = (period['count'] / total_time_anomalies) * 100
                    time_segments.append({
                        'period': period['period'],
                        'count': period['count'],
                        'percentage': percentage,
                        'color': period['color'],
                        'start': cumulative,
                        'width': percentage
                    })
                    cumulative += percentage
            
            # 사용자별 세그먼트 생성
            user_segments = []
            if total_user_anomalies > 0:
                cumulative = 0
                for user in top_users:
                    percentage = (user['count'] / total_user_anomalies) * 100
                    user_segments.append({
                        'user': user['user'],
                        'count': user['count'],
                        'percentage': percentage,
                        'color': user['color'],
                        'start': cumulative,
                        'width': percentage
                    })
                    cumulative += percentage
            
            # HTML 생성
            html = DashboardService._build_summary_html(
                time_segments, user_segments, total_time_anomalies, 
                total_user_anomalies, max_time_period, max_user
            )
            
            return html
            
        except Exception as e:
            print(f"DEBUG: generate_interactive_summary_html 오류: {e}")
            import traceback
            traceback.print_exc()
            return f"<p>종합 설명 생성 중 오류가 발생했습니다: {str(e)}</p>"
    
    @staticmethod
    def _parse_analysis_data(session: AnalysisSession) -> Tuple[List[Dict], List[Dict]]:
        """분석 결과에서 실제 데이터를 파싱하여 차트 데이터를 생성합니다."""
        time_periods = []
        top_users = []
        
        try:
            print(f"DEBUG: parse_analysis_data 시작, session.id={session.id}")
            
            if session.analysis_result and 'result_csv_path' in session.analysis_result:
                csv_path = session.analysis_result['result_csv_path']
                print(f"DEBUG: CSV 경로: {csv_path}")
                
                if not os.path.exists(csv_path):
                    print(f"DEBUG: CSV 파일이 존재하지 않음: {csv_path}")
                    raise FileNotFoundError(f"CSV 파일을 찾을 수 없습니다: {csv_path}")
                
                df = pd.read_csv(csv_path)
                print(f"DEBUG: CSV 로드 성공, shape={df.shape}")
                
                anomaly_df = df[df['Anomaly'] == 1]
                print(f"DEBUG: 이상치 데이터 shape={anomaly_df.shape}")
                
                # 시간 분석
                if not anomaly_df.empty and session.time_col and session.time_col in anomaly_df.columns:
                    time_periods = DashboardService._analyze_time_periods(anomaly_df, session.time_col)
                
                # 사용자 분석
                if not anomaly_df.empty and session.user_col and session.user_col in anomaly_df.columns:
                    top_users = DashboardService._analyze_top_users(anomaly_df, session.user_col)
                
        except Exception as e:
            print(f"DEBUG: 데이터 파싱 오류: {e}")
            import traceback
            traceback.print_exc()
        
        # 기본값 설정
        if not time_periods:
            time_periods = [
                {'period': '새벽시간(00-05시)', 'count': 0, 'color': '#FF6B6B'},
                {'period': '오전시간(06-11시)', 'count': 0, 'color': '#4ECDC4'},
                {'period': '오후시간(12-17시)', 'count': 0, 'color': "#45B7D1"},
                {'period': '저녁시간(18-23시)', 'count': 0, 'color': '#96CEB4'}
            ]
        
        if not top_users:
            top_users = [{'user': '데이터 없음', 'count': 0, 'color': '#D3D3D3'}]
        
        return time_periods, top_users
    
    @staticmethod
    def _analyze_time_periods(anomaly_df: pd.DataFrame, time_col: str) -> List[Dict]:
        """시간대별 이상치 분석"""
        try:
            anomaly_df = anomaly_df.copy()
            anomaly_df[time_col] = pd.to_datetime(anomaly_df[time_col])
            anomaly_df['hour'] = anomaly_df[time_col].dt.hour
            
            def categorize_time(hour):
                if 0 <= hour <= 5:
                    return '새벽시간(00-05시)'
                elif 6 <= hour <= 11:
                    return '오전시간(06-11시)'
                elif 12 <= hour <= 17:
                    return '오후시간(12-17시)'
                else:
                    return '저녁시간(18-23시)'
            
            anomaly_df['time_period'] = anomaly_df['hour'].apply(categorize_time)
            time_counts = anomaly_df['time_period'].value_counts()
            
            colors = ['#FF6B6B', '#4ECDC4', "#45B7D1", '#96CEB4']
            periods = ['새벽시간(00-05시)', '오전시간(06-11시)', '오후시간(12-17시)', '저녁시간(18-23시)']
            
            period_data = []
            for period in periods:
                count = time_counts.get(period, 0)
                period_data.append({'period': period, 'count': int(count)})
            
            period_data.sort(key=lambda x: x['count'], reverse=True)
            
            time_periods = []
            for i, data in enumerate(period_data):
                time_periods.append({
                    'period': data['period'],
                    'count': data['count'],
                    'color': colors[i] if i < len(colors) else '#D3D3D3'
                })
            
            return time_periods
            
        except Exception as e:
            print(f"시간 분석 오류: {e}")
            return []
    
    @staticmethod
    def _analyze_top_users(anomaly_df: pd.DataFrame, user_col: str) -> List[Dict]:
        """상위 사용자별 이상치 분석"""
        try:
            user_counts = anomaly_df[user_col].value_counts().head(4)
            colors = ['#FF6B6B', '#4ECDC4', "#45B7D1", '#96CEB4']
            
            top_users = []
            for i, (user, count) in enumerate(user_counts.items()):
                top_users.append({
                    'user': str(user)[:10],
                    'count': int(count),
                    'color': colors[i] if i < len(colors) else '#D3D3D3'
                })
            
            if len(user_counts) > 4:
                other_count = user_counts.iloc[4:].sum()
                if other_count > 0:
                    top_users.append({
                        'user': '기타',
                        'count': int(other_count),
                        'color': '#D3D3D3'
                    })
            
            return top_users
            
        except Exception as e:
            print(f"사용자 분석 오류: {e}")
            return []
    
    @staticmethod
    def _build_summary_html(time_segments: List[Dict], user_segments: List[Dict],
                          total_time_anomalies: int, total_user_anomalies: int,
                          max_time_period: Optional[Dict], max_user: Optional[Dict]) -> str:
        """요약 HTML을 구성합니다."""
        
        time_bars_html = "".join([
            f'''<div 
                data-name="{seg['period']}"
                data-count="{seg['count']}"
                data-percentage="{seg['percentage']:.1f}"
                style="
                    width: {seg['width']}%;
                    background: {seg['color']};
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: #000;
                    font-size: 16px;
                    font-weight: bold;
                    cursor: pointer;
                    transition: opacity 0.2s;
                    position: relative;
                "
                onmouseover="this.style.opacity='0.8'; showBarTooltip(event, this)"
                onmouseout="this.style.opacity='1'; hideBarTooltip()"
                onmousemove="showBarTooltip(event, this)"
            >
                {seg['count'] if seg['width'] > 8 else ''}
            </div>'''
            for seg in time_segments
        ])
        
        time_legend_html = "".join([
            f'<div style="display: flex; align-items: center; gap: 6px; font-size: 13px;"><div style="width: 14px; height: 14px; background: {seg["color"]}; border-radius: 3px;"></div><span>{seg["period"]} ({seg["count"]}건)</span></div>'
            for seg in time_segments
        ])
        
        user_bars_html = "".join([
            f'''<div 
                data-name="{seg['user']}"
                data-count="{seg['count']}"
                data-percentage="{seg['percentage']:.1f}"
                style="
                    width: {seg['width']}%;
                    background: {seg['color']};
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: #000;
                    font-size: 16px;
                    font-weight: bold;
                    cursor: pointer;
                    transition: opacity 0.2s;
                    position: relative;
                "
                onmouseover="this.style.opacity='0.8'; showBarTooltip(event, this)"
                onmouseout="this.style.opacity='1'; hideBarTooltip()"
                onmousemove="showBarTooltip(event, this)"
            >
                {seg['count'] if seg['width'] > 8 else ''}
            </div>'''
            for seg in user_segments
        ])
        
        user_legend_html = "".join([
            f'<div style="display: flex; align-items: center; gap: 6px; font-size: 13px;"><div style="width: 14px; height: 14px; background: {seg["color"]}; border-radius: 3px;"></div><span>{seg["user"]} ({seg["count"]}건)</span></div>'
            for seg in user_segments
        ])
        
        return f"""
        <div style="display: flex; gap: 2rem; height: 100%;">
            <div style="flex: 1; padding: 1rem;">
                <h4 style="color: #1976d2; margin-bottom: 1rem; border-bottom: 2px solid #e3f2fd; padding-bottom: 0.5rem;">종합 평가</h4>
                
                <div style="margin-bottom: 2rem;">
                    <h5 style="color: #333; margin-bottom: 1rem;"><p style="font-size:1"><b>시간대별 이상 로그 분포 (총 {total_time_anomalies}건)</b></p></h5>
                    <div style="height: 120px; margin-bottom: 1rem; border: 1px solid #eee; border-radius: 8px; padding: 20px; display: flex; flex-direction: column; gap: 15px; justify-content: center;">
                        <div style="position: relative; width: 100%; height: 50px; background: #f5f5f5; border-radius: 8px; overflow: hidden; display: flex;">
                            {time_bars_html}
                        </div>
                        <div style="display: flex; flex-wrap: wrap; gap: 12px; justify-content: center;">
                            {time_legend_html}
                        </div>
                    </div>
                    <p style="color: #666; font-size: 0.95rem; line-height: 1.5; text-align: left;">
                        <b>{f'<span style="color: {max_time_period["color"]}; font-weight: bold;">{max_time_period["period"]}</span>에 가장 많은 이상 로그({max_time_period["count"]}건)가 집중되어 있습니다.' if max_time_period and max_time_period['count'] > 0 else '시간대별 이상 로그가 없거나 고르게 분포되어 있습니다.'}</b>
                    </p>
                </div>
                
                <div>
                    <h5 style="color: #333; margin-bottom: 1rem;"><p style="font-size:1"><b>상위 사용자 이상 로그 개수 (총 {total_user_anomalies}건)</b></p></h5>
                    <div style="height: 120px; margin-bottom: 1rem; border: 1px solid #eee; border-radius: 8px; padding: 20px; display: flex; flex-direction: column; gap: 15px; justify-content: center;">
                        <div style="position: relative; width: 100%; height: 50px; background: #f5f5f5; border-radius: 8px; overflow: hidden; display: flex;">
                            {user_bars_html}
                        </div>
                        <div style="display: flex; flex-wrap: wrap; gap: 12px; justify-content: center;">
                            {user_legend_html}
                        </div>
                    </div>
                    <p style="color: #666; font-size: 0.95rem; line-height: 1.5; text-align: left;">
                        <b>{f'사용자 <span style="color: {max_user["color"]}; font-weight: bold;">{max_user["user"]}</span>에게 가장 많은 이상 로그({max_user["count"]}건)가 집중되어 있습니다.' if max_user and max_user['count'] > 0 else '사용자별 이상 로그 분포를 확인할 수 없습니다.'}</b>
                    </p>
                    <br>
                </div>
            </div>
        </div>
        
        <div id="bar-tooltip" style="
            position: fixed;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 12px;
            pointer-events: none;
            opacity: 0;
            z-index: 10000;
            transition: opacity 0.2s;
        "></div>
        
        <script type="text/javascript">
            function showBarTooltip(event, element) {{
                const tooltip = document.getElementById('bar-tooltip');
                const name = element.getAttribute('data-name');
                const count = element.getAttribute('data-count');
                const percentage = element.getAttribute('data-percentage');
                
                tooltip.innerHTML = `<strong>${{name}}</strong><br/>이상 로그: ${{count}}건<br/>비율: ${{percentage}}%`;
                tooltip.style.left = (event.pageX + 10) + 'px';
                tooltip.style.top = (event.pageY - 28) + 'px';
                tooltip.style.opacity = '1';
            }}
            
            function hideBarTooltip() {{
                const tooltip = document.getElementById('bar-tooltip');
                tooltip.style.opacity = '0';
            }}
        </script>
        """