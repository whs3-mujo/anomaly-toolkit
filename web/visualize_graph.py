import pandas as pd
import plotly.graph_objects as go
import time

# === HEX → RGBA 변환 함수 ===
def hex_to_rgba(hex_color, alpha=0.2):
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return f'rgba({r}, {g}, {b}, {alpha})'

# === 시간대별 이상탐지 시각화 ===
def plot_anomaly_by_hour(df, user_col, time_col, top_n=3):
    print("시간대별 이상탐지 그래프 생성 중...")
    start_time = time.time()
    
    df.columns = df.columns.str.strip()  # 칼럼명 공백 제거
    print("  - 칼럼 정보 확인:", df.columns.tolist())
    print("  - 사용자 컬럼:", user_col)
    print("  - 시간 컬럼:", time_col)
    
    # 사용자 칼럼이 'user'이고 모든 값이 'all'인 경우 처리
    if user_col == 'user' and df[user_col].nunique() == 1 and df[user_col].iloc[0] == 'all':
        print("사용자 칼럼이 'all'로 설정됨 - 전체 사용자 통합 시간대 분석")
        
        # 시간 컬럼이 None이거나 존재하지 않는 경우 처리
        if time_col is None or time_col not in df.columns:
            print("시간 컬럼이 없어서 시간대별 분석을 생략합니다.")
            return None
        
        # 시간 데이터 처리
        try:
            if pd.api.types.is_datetime64_any_dtype(df[time_col]):
                df['hour'] = df[time_col].dt.hour
            else:
                df['datetime_parsed'] = pd.to_datetime(df[time_col], errors='coerce')
                df['hour'] = df['datetime_parsed'].dt.hour
            
            # 2시간 단위로 그룹핑 (기존 스타일과 동일)
            df['hour_bin'] = (df['hour'] // 2) * 2
            hour_bins = list(range(0, 24, 2))
            
            # hour_bin별 이상 로그 수 계산
            hourly_counts = df.groupby('hour_bin').size().reindex(hour_bins, fill_value=0)
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=hourly_counts.index,
                y=hourly_counts.values,
                mode='lines+markers',
                name='All Users',
                line=dict(shape='linear', width=3, color='#4da6ff'),
                fill='tozeroy',
                fillcolor=hex_to_rgba('#4da6ff', alpha=0.2),
                hovertemplate='<b>All Users</b><br>' +
                            'Hour: %{x}<br>' +
                            'Anomaly Count: %{y}<extra></extra>'
            ))
            
            fig.update_layout(
                title='Anomaly By Hour',
                xaxis_title='Hour',
                yaxis_title='Anomaly Count',
                xaxis=dict(
                    tickmode='array',
                    tickvals=hour_bins,
                    ticktext=[str(h) for h in hour_bins],
                    tickangle=0
                ),
                plot_bgcolor='white',
                font=dict(size=12),
                margin=dict(l=40, r=40, t=60, b=40),
                autosize=True,
            )
            
            print(f"전체 사용자 시간대별 그래프 생성 완료")
            return fig.to_html(full_html=False, include_plotlyjs='cdn', 
                             default_width='100%', default_height='100%',
                             config={'responsive': True})
            
        except Exception as e:
            print(f"전체 사용자 시간 처리 중 오류: {e}")
            return None
    
    # 시간 컬럼이 None이거나 존재하지 않는 경우 자동 감지
    if time_col is None or time_col not in df.columns:
        if time_col is None:
            print("시간 컬럼이 지정되지 않아 시간대별 분석을 생략합니다.")
            return None
        
        # 시간 관련 컬럼명 후보들
        time_candidates = [col for col in df.columns 
                          if any(keyword in col.lower() for keyword in 
                                ['time', 'timestamp', 'date', 'datetime', '시간', '날짜'])]
        
        if time_candidates:
            time_col = time_candidates[0]
            print(f"자동 감지된 시간 컬럼: '{time_col}'")
        else:
            print("시간 컬럼을 찾을 수 없습니다. 시간대별 분석이 불가능합니다.")
            print("사용 가능한 컬럼:", df.columns.tolist())
            return None
    
    # 원본 사용자 컬럼명 처리 (.1이 붙은 컬럼이 있으면 그것을 사용)
    actual_user_col = user_col
    if f"{user_col}.1" in df.columns:
        actual_user_col = f"{user_col}.1"
        print(f"원본 사용자 컬럼 '{actual_user_col}' 사용")
    
    df[actual_user_col] = df[actual_user_col].astype(str)
    
    # 시간 칼럼에서 hour 추출
    print("  - 시간 데이터 처리 중...")
    print("    시간 컬럼 샘플:", df[time_col].head())
    print("    시간 컬럼 데이터 타입:", df[time_col].dtype)
    
    # 이미 datetime 타입인지 확인
    if pd.api.types.is_datetime64_any_dtype(df[time_col]):
        df['hour'] = df[time_col].dt.hour
        print("이미 datetime 타입이므로 바로 hour 추출")
    else:
        # 시간 정보가 포함된 포맷만 시도 (날짜만 있는 포맷 제외)
        time_formats_to_try = [
            "%Y.%m.%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M", 
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%Y.%m.%d %H:%M:%S",
            "%Y%m%d %H:%M:%S",
            "%Y%m%d %H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S.%f",
            "%d-%m-%Y %H:%M:%S",
            "%d-%m-%Y %H:%M",
            "%d.%m.%Y %H:%M:%S",
            "%d.%m.%Y %H:%M",
            "%Y년 %m월 %d일 %H:%M:%S",
            "%Y년 %m월 %d일 %H:%M",
            "%m/%d/%y %H:%M:%S",
            "%m/%d/%y %H:%M",
            "%d/%m/%y %H:%M:%S",
            "%d/%m/%y %H:%M",
            "%y-%m-%d %H:%M:%S",
            "%y-%m-%d %H:%M",
            "%y.%m.%d %H:%M:%S",
            "%y.%m.%d %H:%M",
            "%H:%M:%S",
            "%H:%M"
        ]
        
        success = False
        for fmt in time_formats_to_try:
            try:
                parsed_datetime = pd.to_datetime(df[time_col], format=fmt, errors='coerce')
                if not parsed_datetime.isna().all():
                    df['hour'] = parsed_datetime.dt.hour
                    print(f"포맷 '{fmt}'로 hour 추출 성공")
                    success = True
                    break
            except:
                continue
        
        # 시간 정보가 포함된 포맷으로 실패한 경우, 자동 파싱 시도하되 시간 정보 확인
        if not success:
            try:
                parsed_datetime = pd.to_datetime(df[time_col], errors='coerce')
                if not parsed_datetime.isna().all():
                    # 시간 정보가 실제로 있는지 확인 (모든 시간이 00:00:00인지 체크)
                    sample_times = parsed_datetime.dropna().dt.time.unique()
                    has_time_info = len(sample_times) > 1 or (len(sample_times) == 1 and sample_times[0] != pd.Timestamp('00:00:00').time())
                    
                    if has_time_info:
                        df['hour'] = parsed_datetime.dt.hour
                        print("자동 파싱으로 hour 추출 성공 (시간 정보 확인됨)")
                        success = True
                    else:
                        print("날짜만 있고 시간 정보가 없는 데이터입니다. 시간대별 분석이 불가능합니다.")
                        return None
            except Exception as e:
                print(f"자동 파싱 실패: {e}")
    
    # 시간 정보가 제대로 추출되었는지 확인
    if not success or df['hour'].isna().all():
        print(f"'{time_col}'에서 시간 정보 추출 실패! 시간대별 분석이 불가능합니다.")
        print("시간 칼럼 샘플 데이터:")
        print(df[time_col].head(10))
        return None
    
    print("hour 추출 샘플:", df['hour'].head())
    print("hour NaN 개수:", df['hour'].isna().sum())
    
    if df['hour'].isna().all():
        print(f"'{time_col}'에서 hour 추출 실패! 날짜/시간 형식 확인 필요.")
        print("시간 칼럼 샘플 데이터:")
        print(df[time_col].head(10))
        return None

    df['hour_bin'] = (df['hour'] // 2) * 2  # 2시간 단위
    
    # 디버깅: 실제 hour와 hour_bin 매핑 확인
    print("시간 그룹핑 예시:")
    hour_mapping = df[['hour', 'hour_bin']].drop_duplicates().sort_values('hour')
    for _, row in hour_mapping.head(10).iterrows():
        print(f"   {int(row['hour']):02d}시 → {int(row['hour_bin']):02d}시 그룹")

    # 이상 로그만 필터링해서 상위 사용자 찾기
    if 'Anomaly' in df.columns:
        anomaly_df = df[df['Anomaly'] == 1]
        top_users = anomaly_df[actual_user_col].value_counts().nlargest(top_n).index.tolist()
        print(f"이상 로그 {len(anomaly_df)}건에서 상위 {top_n}명 사용자 추출")
    else:
        top_users = df[actual_user_col].value_counts().nlargest(top_n).index.tolist()
        print(f"전체 데이터 {len(df)}건에서 상위 {top_n}명 사용자 추출 (이미 필터링된 것으로 간주)")
    
    for i, user in enumerate(top_users):
        if 'Anomaly' in df.columns:
            user_anomaly_count = len(df[(df[actual_user_col] == user) & (df['Anomaly'] == 1)])
        else:
            user_anomaly_count = len(df[df[actual_user_col] == user])
        print(f"   - {user}: {user_anomaly_count}건")
    
    hour_bins = list(range(0, 24, 2))  # 2시간 단위로 변경

    # 시간대별 그룹핑 시에도 이상 로그만 사용
    if 'Anomaly' in df.columns:
        plot_df = df[df['Anomaly'] == 1]
    else:
        plot_df = df
    
    hourly_counts = (
        plot_df[plot_df[actual_user_col].isin(top_users)]
        .groupby(['hour_bin', actual_user_col])
        .size()
        .unstack()
        .fillna(0)
        .reindex(hour_bins, fill_value=0)
    )

    colors = ['#4da6ff', '#ff6666', '#80cc28', '#cc66ff', '#ffaa00']
    fig = go.Figure()

    # 전체 이상치 개수 계산 (Anomaly == 1 인 것만)
    anomaly_df = df[df['Anomaly'] == 1] if 'Anomaly' in df.columns else df
    total_anomalies = len(anomaly_df)

    for i, user in enumerate(top_users):
        user_anomaly_count = len(anomaly_df[anomaly_df[actual_user_col] == user])
        
        if top_n == 10:
            percent = (user_anomaly_count / total_anomalies) * 100 if total_anomalies > 0 else 0
            display_name = f"{user} ({user_anomaly_count}건, {percent:.1f}%)"
        else:
            display_name = user[:5] + "..." if len(user) > 5 else user

        fig.add_trace(go.Scatter(
            x=hourly_counts.index,
            y=hourly_counts[user],
            mode='lines+markers',
            name=display_name,
            line=dict(shape='linear', width=3, color=colors[i % len(colors)]),
            fill='tozeroy',
            fillcolor=hex_to_rgba(colors[i % len(colors)], alpha=0.2),
            hovertemplate='<b>%s</b><br>' % user +
                        'Hour: %{x}<br>' +
                        'Anomaly Count: %{y}<extra></extra>',
            visible='legendonly' if top_n == 10 else True
        ))


    fig.update_layout(
        title='Anomaly By Hour',
        xaxis_title='Hour',
        yaxis_title='Anomaly Count',
        xaxis=dict(
            tickmode='array',
            tickvals=hour_bins,
            ticktext=[str(h) for h in hour_bins],
            tickangle=0  # 시간 라벨을 가로로 표시
        ),
        plot_bgcolor='white',
        font=dict(size=12),  # 글자 크기를 16에서 12로 줄임
        margin=dict(l=40, r=40, t=60, b=40),
        autosize=True,  # ★ 추가
    )

    fig_html = fig.to_html(
        full_html=False,
        include_plotlyjs='cdn',
        default_width='100%',
        default_height='100%',
        config={'responsive': True}
    )

    elapsed_time = time.time() - start_time
    print(f"시간대별 이상탐지 그래프 생성 완료 ({elapsed_time:.2f}초)")
    return fig_html

# === 사용자별 이상탐지 시각화 ===
def plot_anomaly_by_user(df, user_col, top_n=10, show_more=False):
    print("사용자별 이상탐지 그래프 생성 중...")
    start_time = time.time()
    
    # 사용자 칼럼이 'user'이고 모든 값이 'all'인 경우 처리
    if user_col == 'user' and df[user_col].nunique() == 1 and df[user_col].iloc[0] == 'all':
        print("사용자 칼럼이 'all'로 설정됨 - 전체 사용자 통합 분석")
        
        # 이상 로그만 필터링 (안전장치)
        if 'Anomaly' in df.columns:
            anomaly_df = df[df['Anomaly'] == 1]
            total_anomalies = len(anomaly_df)
        else:
            total_anomalies = len(df)
        
        fig = go.Figure([go.Bar(
            x=['All Users'],
            y=[total_anomalies],
            marker=dict(color=['#ff4d4d']),  # 기존 스타일과 동일한 색상
            hovertemplate='<b>All Users</b><br>' +
                         'Anomaly Count: %{y}<br>' +
                         'Total Ratio: 100.0%<extra></extra>'
        )])
        
        fig.update_layout(
            title='Anomalies by User',
            xaxis_title='User',
            yaxis_title='Anomaly Count',
            xaxis=dict(showticklabels=False),  # X축 사용자 이름 숨기기 (기존 스타일)
            plot_bgcolor='white',
            font=dict(size=12),
            margin=dict(l=40, r=40, t=60, b=40),
            autosize=True,
        )
        
        fig_html = fig.to_html(
            full_html=False,
            include_plotlyjs='cdn',
            default_width='100%',
            default_height='100%',
            config={'responsive': True}
        )
        
        print(f"전체 사용자 그래프 생성 완료 (총 {total_anomalies}건)")
        return fig_html
    
    # 원본 사용자 컬럼명 처리 (.1이 붙은 컬럼이 있으면 그것을 사용)
    actual_user_col = user_col
    if f"{user_col}.1" in df.columns:
        actual_user_col = f"{user_col}.1"
        print(f"원본 사용자 컬럼 '{actual_user_col}' 사용")
    
    df[actual_user_col] = df[actual_user_col].astype(str)
    
    # 이상 로그만 필터링 (안전장치)
    if 'Anomaly' in df.columns:
        anomaly_df = df[df['Anomaly'] == 1]
        print(f"전체 로그 {len(df)}건 중 이상 로그 {len(anomaly_df)}건으로 필터링")
        
        # 이상 로그가 없는 경우 처리
        if len(anomaly_df) == 0:
            print("이상 로그가 없습니다. 빈 그래프를 반환합니다.")
            fig = go.Figure()
            fig.update_layout(
                title='Anomalies by User (No Anomalies Found)',
                xaxis_title='User',
                yaxis_title='Anomaly Count',
                annotations=[dict(text="이상 로그가 발견되지 않았습니다.", 
                                x=0.5, y=0.5, showarrow=False, 
                                font=dict(size=16))]
            )
            return fig.to_html(full_html=False, include_plotlyjs='cdn')
        
        # 전체 이상 사용자 수 확인
        total_anomaly_users = len(anomaly_df[actual_user_col].unique())
        print(f"전체 이상 사용자 수: {total_anomaly_users}명")
        
        # 기본 10명 표시 로직
        if not show_more:
            # 이상 사용자가 10명 이하인 경우 그 수만큼, 10명 이상인 경우 10명까지
            display_count = min(10, total_anomaly_users)
        else:
            # 더보기: 최소 5명 또는 전체 이상 사용자의 20% 중 더 큰 값을 추가
            additional_by_percent = int(total_anomaly_users * 0.2)  # 전체의 20%
            additional_count = max(5, additional_by_percent)
            display_count = min(10 + additional_count, total_anomaly_users)
        
        print(f"표시할 사용자 수: {display_count}명 (show_more: {show_more})")
        
        # 사용자별 이상 로그 카운트 (원본 컬럼 사용)
        user_counts = anomaly_df[actual_user_col].value_counts().nlargest(display_count)
        print(f"상위 {display_count}명 사용자별 이상 로그 수:")
        for user, count in user_counts.items():
            print(f"   - {user}: {count}건")
    else:
        # Anomaly 컬럼이 없으면 전체 데이터 사용 (이미 필터링된 것으로 간주)
        print(f"'Anomaly' 컬럼이 없어 전체 데이터 {len(df)}건을 사용합니다.")
        
        # 전체 사용자 수 확인
        total_users = len(df[actual_user_col].unique())
        print(f"전체 사용자 수: {total_users}명")
        
        # 기본 10명 표시 로직
        if not show_more:
            display_count = min(10, total_users)
        else:
            # 더보기: 최소 5명 또는 전체 사용자의 20% 중 더 큰 값을 추가
            additional_by_percent = int(total_users * 0.2)  # 전체의 20%
            additional_count = max(5, additional_by_percent)  # 최소 5명 보장
            display_count = min(10 + additional_count, total_users)
        
        print(f"표시할 사용자 수: {display_count}명 (show_more: {show_more})")
        
        user_counts = df[actual_user_col].value_counts().nlargest(display_count)
        print(f"상위 {display_count}명 사용자별 로그 수:")
        for user, count in user_counts.items():
            print(f"   - {user}: {count}건")

    colors = ['#ff4d4d'] + ['#4da6ff'] * (len(user_counts) - 1)

    fig = go.Figure([go.Bar(
        x=user_counts.index,
        y=user_counts.values,
        marker=dict(color=colors),
        hovertemplate='<b>%{x}</b><br>' +
                     'Anomaly Count: %{y}<br>' +
                     'Total Ratio: %{customdata:.1%}<extra></extra>',
        customdata=user_counts.values / user_counts.sum()  # 비율 계산
    )])

    fig.update_layout(
        title='Anomalies by User',
        xaxis_title='User',
        yaxis_title='Anomaly Count',
        xaxis=dict(
            showticklabels=True,  # X축 사용자 이름 항상 표시
            tickangle=45,  # 사용자명이 겹치지 않도록 45도 회전
            tickfont=dict(size=10)  # 글자 크기 조정
        ),
        plot_bgcolor='white',
        font=dict(size=12),  # 글자 크기
        margin=dict(l=40, r=40, t=60, b=80),  # 하단 마진 증가 (회전된 텍스트 공간)
        autosize=True, 
    )
    fig_html = fig.to_html(
        full_html=False,
        include_plotlyjs='cdn',
        default_width='100%',
        default_height='100%',
        config={'responsive': True}
    )

    elapsed_time = time.time() - start_time
    print(f"사용자별 이상탐지 그래프 생성 완료 ({elapsed_time:.2f}초)")
    return fig_html

# === 이상치 점수 분포 시각화 ===
def plot_anomaly_score_distribution(df, threshold=-0.2, score_col=None):
    print("이상치 점수 분포 그래프 생성 중...")
    start_time = time.time()
    
    import plotly.graph_objects as go
    import pandas as pd

    # anomaly_score 컬럼명 직접 감지 (대소문자, 공백, 언더스코어 무시)
    if score_col is None:
        score_col_candidates = [
            col for col in df.columns
            if col.lower().replace(" ", "_") in ["anomaly_score", "anomaly_score", "anomaly score"]
        ]
        if score_col_candidates:
            score_col = score_col_candidates[0]
        else:
            score_candidates = [
                col for col in df.columns
                if pd.api.types.is_numeric_dtype(df[col])
            ]
            if not score_candidates:
                print("DataFrame에 'anomaly_score' 스타일의 수치형 컬럼이 없습니다.")
                return
            score_col = score_candidates[0]
        print(f"자동 감지된 anomaly score 컬럼: '{score_col}'")
    else:
        if score_col not in df.columns:
            print(f"'{score_col}' 컬럼이 DataFrame에 없습니다.")
            return

    if 'Anomaly' not in df.columns:
        print("'Anomaly' 컬럼이 없어 이상치 분리 시각화는 불가능합니다.")
        return

    df_normal = df[df['Anomaly'] == 0]
    df_anomaly = df[df['Anomaly'] == 1]

    fig = go.Figure()

    fig.add_trace(go.Histogram(
        x=df_normal[score_col],
        nbinsx=50,
        name='Normal',
        marker_color='lightskyblue',
        opacity=0.75
    ))

    fig.add_trace(go.Histogram(
        x=df_anomaly[score_col],
        nbinsx=50,
        name='Anomaly',
        marker_color='indianred',
        opacity=0.85
    ))

    fig.add_shape(
        type="line",
        x0=threshold,
        x1=threshold,
        y0=0,
        y1=max(
            df_normal[score_col].value_counts().max(),
            df_anomaly[score_col].value_counts().max()
        ),
        line=dict(color='black', dash='dash'),
        name='Threshold'
    )

    fig.update_layout(
        title="Anomaly Score Distribution",
        xaxis_title=score_col,
        yaxis_title="Count",
        bargap=0.1,
        template="simple_white",
        barmode='overlay',
        autosize=True,  # ★ 추가
    )

    fig_html = fig.to_html(
        full_html=False,
        include_plotlyjs='cdn',
        default_width='100%',
        default_height='100%',
        config={'responsive': True}
    )

    elapsed_time = time.time() - start_time
    print(f"이상치 점수 분포 그래프 생성 완료 ({elapsed_time:.2f}초)")
    return fig_html
