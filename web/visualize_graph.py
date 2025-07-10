import pandas as pd
import plotly.graph_objects as go

# -------------------------------------
# ✅ 사용자 및 시간 컬럼 자동 감지
# -------------------------------------
def detect_user_and_time_columns(df):
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

    user_col, time_col = None, None

    # ✅ 1차: '.1'로 끝나는 컬럼 중 사용자 후보 찾기
    for col in df.columns:
        if col.endswith('.1') and any(c in col.lower() for c in user_candidates):
            user_col = col
            break

    # ✅ 2차: 일반적인 사용자 컬럼 찾기
    if user_col is None:
        for col in df.columns:
            if any(c in col.lower() for c in user_candidates):
                user_col = col
                break

    # ✅ 3차: 범주형 비율 기반 추정
    if user_col is None:
        for col in df.select_dtypes(include='object'):
            ratio = df[col].nunique() / len(df)
            if 0.01 < ratio < 0.5:
                user_col = col
                break

    if user_col is None:
        print("❓ 사용자 컬럼을 자동으로 감지하지 못했습니다.")
        print("컬럼 목록:", df.columns.tolist())
        user_col = input("사용자 컬럼명을 직접 입력해주세요: ")

    # ✅ 시간 컬럼 자동 감지
    for col in df.columns:
        try:
            parsed = pd.to_datetime(df[col], errors='coerce')
            if parsed.notna().mean() > 0.9:
                time_col = col
                break
        except:
            continue
    if time_col is None:
        for col in df.columns:
            if any(c in col.lower() for c in time_candidates):
                time_col = col
                break
    if time_col is None:
        print("❓ 시간 컬럼을 자동으로 감지하지 못했습니다.")
        print("컬럼 목록:", df.columns.tolist())
        time_col = input("시간 컬럼명을 직접 입력해주세요: ")

    print(f"✅ 감지된 사용자 컬럼: {user_col}, 시간 컬럼: {time_col}")
    return user_col, time_col


# -------------------------------------
# 🎨 HEX → RGBA 변환 함수
# -------------------------------------
#색상 코드에 투명도(alpha)를 입혀서 시각적으로 부드럽고 겹침 표현이 가능한 그래프 만듬
def hex_to_rgba(hex_color, alpha=0.2):
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return f'rgba({r}, {g}, {b}, {alpha})'


# -------------------------------------
# 📊 시간대별 이상탐지 시각화
# -------------------------------------
def plot_anomaly_by_hour(df, user_col, time_col, top_n=3):
    df[user_col] = df[user_col].astype(str)
    df['hour'] = pd.to_datetime(df[time_col], errors='coerce').dt.hour
    df['hour_bin'] = (df['hour'] // 2) * 2  # 2시간 단위

    top_users = df[user_col].value_counts().nlargest(top_n).index.tolist()
    hour_bins = list(range(0, 24, 2))

    hourly_counts = (
        df[df[user_col].isin(top_users)]
        .groupby(['hour_bin', user_col])
        .size()
        .unstack()
        .fillna(0)
        .reindex(hour_bins, fill_value=0)
    )

    colors = ['#4da6ff', '#ff6666', '#80cc28', '#cc66ff', '#ffaa00']
    fig = go.Figure()

    for i, user in enumerate(top_users):
        fig.add_trace(go.Scatter(
            x=hourly_counts.index,
            y=hourly_counts[user],
            mode='lines+markers',
            name=user,
            line=dict(shape='linear', width=3, color=colors[i % len(colors)]),  # 👉 직선
            fill='tozeroy',
            fillcolor=hex_to_rgba(colors[i % len(colors)], alpha=0.2)
        ))

    fig.update_layout(
        title='Anomaly By Hour',  # 제목 
        xaxis_title='Hour',       # X축 이름
        yaxis_title='Anomaly Count',
        xaxis=dict(
            tickmode='array',
            tickvals=hour_bins,
            ticktext=[str(h) for h in hour_bins]
        ),
        plot_bgcolor='white',
        font=dict(size=16),
        margin=dict(l=40, r=40, t=60, b=40),
    )

    fig.show()
# -------------------------------------
# 📊 사용자별 이상탐지 시각화
# -------------------------------------
def plot_anomaly_by_user(df, user_col, top_n=5):
    df[user_col] = df[user_col].astype(str)
    user_counts = df[user_col].value_counts().nlargest(top_n)

    # 색상 설정: 1등은 빨간색, 나머지는 파란색
    colors = ['#ff4d4d'] + ['#4da6ff'] * (len(user_counts) - 1)

    fig = go.Figure([go.Bar(
        x=user_counts.index,
        y=user_counts.values,
        marker=dict(color=colors)
    )])

    fig.update_layout(
        title='Anomalies by User',
        xaxis_title='User',
        yaxis_title='Anomaly Count',
        plot_bgcolor='white',
        font=dict(size=16),
        margin=dict(l=40, r=40, t=60, b=40),
    )
    fig.show()

# -------------------------------------
# 📊 이상치 점수 분포 시각화
# -------------------------------------
def plot_anomaly_score_distribution(df, threshold=-0.2, score_col=None):
    import plotly.graph_objects as go
    import pandas as pd

    # 🎯 anomaly_score 또는 사용자 지정 컬럼 자동 감지
    if score_col is None:
        score_candidates = [
            col for col in df.columns
            if pd.api.types.is_numeric_dtype(df[col])
            and df[col].nunique() > 10
            and df[col].min() < 0
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

    # ✅ 이상치/정상치 분리
    if 'Anomaly' not in df.columns:
        print("⚠️ 'Anomaly' 컬럼이 없어 이상치 분리 시각화는 불가능합니다.")
        return

    df_normal = df[df['Anomaly'] == 0]
    df_anomaly = df[df['Anomaly'] == 1]

    # 📊 Plotly 시각화
    fig = go.Figure()

    # 정상 로그 히스토그램 (파란색)
    fig.add_trace(go.Histogram(
        x=df_normal[score_col],
        nbinsx=50,
        name='Normal',
        marker_color='lightskyblue',
        opacity=0.75
    ))

    # 이상 로그 히스토그램 (빨간색)
    fig.add_trace(go.Histogram(
        x=df_anomaly[score_col],
        nbinsx=50,
        name='Anomaly',
        marker_color='indianred',
        opacity=0.85
    ))

    # Threshold 점선
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
        barmode='overlay'
    )

    fig.show()