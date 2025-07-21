import pandas as pd
import plotly.graph_objects as go
import time

# -------------------------------------
# ✅ 사용자 및 시간 컬럼 자동 감지 (수동 선택 지원)
# -------------------------------------
def detect_user_and_time_columns(df, user_col=None, time_col=None):
    print("🔍 사용자 및 시간 컬럼 자동 감지 시작...")
    
    user_candidates = [
        'user', 'user_id', 'userid', 'username', 'login', 'login_id', 'login_user',
        'account', 'account_id', 'acct', 'acct_id', 'member', 'member_id',
        'employee', 'employee_id', 'emp_id', 'staff', 'staff_id',
        'operator', 'operator_id', 'person', 'person_id', 'personnel_id',
        'admin_user', 'manager', 'admin_id', 'internal_user', 'internal_account',
        'actor', 'subject', 'caller', 'initiator', 'requester',
        'principal', 'principal_id', 'identity', 'identity_id',
        'user_principal_name', 'upn', 'customer', 'customer_id', 'client', 'client_id',
        'account_holder', 'account_user', 'bank_user', 'trader_id', 'agent_id',
        'civil_id', 'student_id', 'teacher_id', 'patient_id', 'resident_id', 'ssn', 'national_id',
        'iam_user', 'aws_user', 'azure_user', 'gcp_user',
        'assumed_role_user', 'role_user', 'service_user', 'user_identity', 'subject_identity'
    ]
    time_candidates = ['timestamp', 'time', 'datetime', 'date', 'event_time', 'logtime']

    # ✅ 프론트에서 선택한 값이 있으면 우선 사용
    if user_col is not None and user_col in df.columns:
        pass
    else:
        # 자동 감지
        user_col = None
        for col in df.columns: # ✅ 1차: 일반적인 사용자 컬럼 찾기
            if any(c in col.lower() for c in user_candidates):
                user_col = col
                break
        if user_col is None: # ✅ 2차: 범주형 비율 기반 추정 (더 엄격하게 개선)
            for col in df.select_dtypes(include='object'):
                if any(c in col.lower() for c in user_candidates): # 1. 컬럼명에 user_candidates 일부라도 포함된 경우는 이미 1차에서 잡혔으니 패스
                    continue
                nunique = df[col].nunique()
                ratio = nunique / len(df)
                if 0.05 < ratio < 0.5 and nunique >= 5: # 2. 고유값 비율과 개수 조건을 더 엄격하게
                    # 3. 컬럼명에 너무 일반적인 단어(예: code, type, status 등) 포함 시 제외
                    if not any(ex in col.lower() for ex in ['code', 'type', 'status', 'level', 'flag']):
                        user_col = col
                        break
        # ✅ 3차: 직접 입력
        if user_col is None:
            print("❓ 사용자 컬럼을 자동으로 감지하지 못했습니다.")
            print("컬럼 목록:", df.columns.tolist())
            user_col = input("사용자 컬럼명을 직접 입력해주세요: ")

    if time_col is not None and time_col in df.columns:
        pass
    else:
        # 자동 감지
        time_col = None # ✅ 1차: 일반적인 시간 컬럼 찾기
        for col in df.columns:
            try:
                parsed = pd.to_datetime(df[col], errors='coerce') # 날짜 형식으로 변환 시도
                if parsed.notna().mean() > 0.9: # 90% 이상이 날짜 형식이면 유효한 시간 컬럼으로 간주
                    time_col = col 
                    break 
            except:
                continue
        if time_col is None: # ✅ 2차: 범주형 비율 기반 추정
            for col in df.columns: 
                if any(c in col.lower() for c in time_candidates): # 1. 컬럼명에 time_candidates 일부라도 포함된 경우는 이미 1차에서 잡혔으니 패스
                    time_col = col 
                    break
        if time_col is None: # ✅ 3차: 직접 입력
            print("❓ 시간 컬럼을 자동으로 감지하지 못했습니다.")
            print("컬럼 목록:", df.columns.tolist())
            print("time_col:", time_col)
            time_col = input("시간 컬럼명을 직접 입력해주세요: ")

    print(f"✅ 감지된 사용자 컬럼: {user_col}, 시간 컬럼: {time_col}")
    return user_col, time_col

# -------------------------------------
# 🎨 HEX → RGBA 변환 함수
# -------------------------------------
def hex_to_rgba(hex_color, alpha=0.2):
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return f'rgba({r}, {g}, {b}, {alpha})'

# -------------------------------------
# 📊 시간대별 이상탐지 시각화
# -------------------------------------
def plot_anomaly_by_hour(df, user_col, time_col, top_n=3):
    print("📊 시간대별 이상탐지 그래프 생성 중...")
    start_time = time.time()
    
    df.columns = df.columns.str.strip()  # 칼럼명 공백 제거
    print("  - 칼럼 정보 확인:", df.columns.tolist())
    print("  - 사용자 컬럼:", user_col)
    print("  - 시간 컬럼:", time_col)
    
    # 원본 사용자 컬럼명 처리 (.1이 붙은 컬럼이 있으면 그것을 사용)
    actual_user_col = user_col
    if f"{user_col}.1" in df.columns:
        actual_user_col = f"{user_col}.1"
        print(f"✅ 원본 사용자 컬럼 '{actual_user_col}' 사용")
    
    df[actual_user_col] = df[actual_user_col].astype(str)
    
    # 시간 칼럼에서 hour 추출 (더 견고한 방식)
    print("  - 시간 데이터 처리 중...")
    print("    시간 컬럼 샘플:", df[time_col].head())
    print("    시간 컬럼 데이터 타입:", df[time_col].dtype)
    
    # 이미 datetime 타입인지 확인
    if pd.api.types.is_datetime64_any_dtype(df[time_col]):
        df['hour'] = df[time_col].dt.hour
        print("✅ 이미 datetime 타입이므로 바로 hour 추출")
    else:
        # 다양한 포맷 시도
        formats_to_try = [
            "%Y.%m.%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M", 
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M"
        ]
        
        success = False
        for fmt in formats_to_try:
            try:
                df['hour'] = pd.to_datetime(df[time_col], format=fmt, errors='coerce').dt.hour
                if not df['hour'].isna().all():
                    print(f"✅ 포맷 '{fmt}'로 hour 추출 성공")
                    success = True
                    break
            except:
                continue
        
        # 모든 포맷 실패 시 자동 파싱 시도
        if not success:
            try:
                df['hour'] = pd.to_datetime(df[time_col], errors='coerce').dt.hour
                if not df['hour'].isna().all():
                    print("✅ 자동 파싱으로 hour 추출 성공")
                    success = True
            except Exception as e:
                print(f"❌ 자동 파싱 실패: {e}")
    
    print("hour 추출 샘플:", df['hour'].head())
    print("hour NaN 개수:", df['hour'].isna().sum())
    
    if df['hour'].isna().all():
        print(f"⚠️ '{time_col}'에서 hour 추출 실패! 날짜/시간 형식 확인 필요.")
        print("시간 칼럼 샘플 데이터:")
        print(df[time_col].head(10))
        return

    df['hour_bin'] = (df['hour'] // 2) * 2  # 2시간 단위
    
    # 디버깅: 실제 hour와 hour_bin 매핑 확인
    print("🔍 시간 그룹핑 예시:")
    hour_mapping = df[['hour', 'hour_bin']].drop_duplicates().sort_values('hour')
    for _, row in hour_mapping.head(10).iterrows():
        print(f"   {int(row['hour']):02d}시 → {int(row['hour_bin']):02d}시 그룹")

    # 이상 로그만 필터링해서 상위 사용자 찾기
    if 'Anomaly' in df.columns:
        anomaly_df = df[df['Anomaly'] == 1]
        top_users = anomaly_df[actual_user_col].value_counts().nlargest(top_n).index.tolist()
        print(f"✅ 이상 로그 {len(anomaly_df)}건에서 상위 {top_n}명 사용자 추출")
    else:
        top_users = df[actual_user_col].value_counts().nlargest(top_n).index.tolist()
        print(f"✅ 전체 데이터 {len(df)}건에서 상위 {top_n}명 사용자 추출 (이미 필터링된 것으로 간주)")
    
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

    for i, user in enumerate(top_users):
        # 사용자 이름을 5글자로 제한
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
    print(f"✅ 시간대별 이상탐지 그래프 생성 완료 ({elapsed_time:.2f}초)")
    return fig_html

# -------------------------------------
# 📊 사용자별 이상탐지 시각화
# -------------------------------------
def plot_anomaly_by_user(df, user_col, top_n=5):
    print("📊 사용자별 이상탐지 그래프 생성 중...")
    start_time = time.time()
    
    # 원본 사용자 컬럼명 처리 (.1이 붙은 컬럼이 있으면 그것을 사용)
    actual_user_col = user_col
    if f"{user_col}.1" in df.columns:
        actual_user_col = f"{user_col}.1"
        print(f"✅ 원본 사용자 컬럼 '{actual_user_col}' 사용")
    
    df[actual_user_col] = df[actual_user_col].astype(str)
    
    # 이상 로그만 필터링 (안전장치)
    if 'Anomaly' in df.columns:
        anomaly_df = df[df['Anomaly'] == 1]
        print(f"✅ 전체 로그 {len(df)}건 중 이상 로그 {len(anomaly_df)}건으로 필터링")
        
        # 이상 로그가 없는 경우 처리
        if len(anomaly_df) == 0:
            print("⚠️ 이상 로그가 없습니다. 빈 그래프를 반환합니다.")
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
        
        # 사용자별 이상 로그 카운트 (원본 컬럼 사용)
        user_counts = anomaly_df[actual_user_col].value_counts().nlargest(top_n)
        print(f"✅ 상위 {top_n}명 사용자별 이상 로그 수:")
        for user, count in user_counts.items():
            print(f"   - {user}: {count}건")
    else:
        # Anomaly 컬럼이 없으면 전체 데이터 사용 (이미 필터링된 것으로 간주)
        print(f"⚠️ 'Anomaly' 컬럼이 없어 전체 데이터 {len(df)}건을 사용합니다.")
        user_counts = df[actual_user_col].value_counts().nlargest(top_n)
        print(f"✅ 상위 {top_n}명 사용자별 로그 수:")
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
        xaxis=dict(showticklabels=False),  # X축 사용자 이름 숨기기
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
    print(f"✅ 사용자별 이상탐지 그래프 생성 완료 ({elapsed_time:.2f}초)")
    return fig_html

# -------------------------------------
# 📊 이상치 점수 분포 시각화
# -------------------------------------
def plot_anomaly_score_distribution(df, threshold=-0.2, score_col=None):
    print("📊 이상치 점수 분포 그래프 생성 중...")
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
                print("⚠️ DataFrame에 'anomaly_score' 스타일의 수치형 컬럼이 없습니다.")
                return
            score_col = score_candidates[0]
        print(f"✅ 자동 감지된 anomaly score 컬럼: '{score_col}'")
    else:
        if score_col not in df.columns:
            print(f"❌ '{score_col}' 컬럼이 DataFrame에 없습니다.")
            return

    if 'Anomaly' not in df.columns:
        print("⚠️ 'Anomaly' 컬럼이 없어 이상치 분리 시각화는 불가능합니다.")
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
    print(f"✅ 이상치 점수 분포 그래프 생성 완료 ({elapsed_time:.2f}초)")
    return fig_html