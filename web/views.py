from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from .forms import UploadFileForm
from .models import AnalysisSession
import uuid
import json
import os
from django.conf import settings
import pandas as pd
from .ai_script import detect_anomalies
from .visualize_graph import plot_anomaly_by_hour, plot_anomaly_by_user, plot_anomaly_score_distribution
import time
import threading

def redirect_dashboard(request):
    return redirect('web:dashboard')

def dashboard_view(request):
    return render(request, 'web/dashboard.html')

def get_analysis_history(request):
    """분석 히스토리 목록 반환"""
    try:
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
        return JsonResponse({
            'success': True,
            'history': history_data,
            'total': len(history_data)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)

@require_http_methods(["GET"])
def get_analysis_detail(request, session_id):
    """특정 분석 결과 상세 정보 반환"""
    try:
        session = get_object_or_404(AnalysisSession, session_id=session_id)
        return JsonResponse({
            'success': True,
            'session': {
                'id': session.id,
                'session_id': session.session_id,
                'filename': session.original_filename,
                'file_type': session.file_type,
                'created_at': session.created_at.strftime('%Y-%m-%dT%H:%M:%SZ'),
                'analysis_result': session.analysis_result,
                'user_graph_html': getattr(session, 'user_graph_html', None),
                'hour_graph_html': getattr(session, 'hour_graph_html', None),
                'score_graph_html': getattr(session, 'score_graph_html', None),
            }
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)

def create_analysis_session(filename, file_path, file_type, analysis_result):
    """새로운 분석 세션 생성 (완료된 분석 결과와 함께)"""
    session_id = str(uuid.uuid4())
    analysis_session = AnalysisSession.objects.create(
        session_id=session_id,
        original_filename=filename,
        file_path=file_path,
        file_type=file_type,
        analysis_result=analysis_result
    )
    return analysis_session

@csrf_exempt
@require_http_methods(["DELETE"])
def delete_analysis_session(request, session_id):
    """분석 세션 삭제"""
    try:
        session = get_object_or_404(AnalysisSession, session_id=session_id)
        session.delete()
        return JsonResponse({'success': True, 'message': '분석 기록이 삭제되었습니다.'})
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def rename_analysis_session(request, session_id):
    """분석 세션 이름 변경"""
    try:
        session = get_object_or_404(AnalysisSession, session_id=session_id)
        data = json.loads(request.body)
        new_filename = data.get('filename', '').strip()
        if not new_filename:
            return JsonResponse({'success': False, 'error': '파일명을 입력해주세요.'}, status=400)
        session.original_filename = new_filename
        session.save()
        return JsonResponse({'success': True, 'message': '파일명이 변경되었습니다.'})
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)

@require_http_methods(["GET", "POST"])
def upload_view(request):
    if request.method == "POST":
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            file = form.cleaned_data['datafile']
            try:
                save_dir = os.path.join(settings.MEDIA_ROOT, "uploads")
                os.makedirs(save_dir, exist_ok=True)
                save_path = os.path.join(save_dir, file.name)
                with open(save_path, "wb+") as dest:
                    for chunk in file.chunks():
                        dest.write(chunk)
                print(f"파일 저장 완료: {save_path}")

                analysis_result = detect_anomalies(save_path)
                print(f"분석 결과: {analysis_result}")

                # 업로드만 하는 경우에는 그래프 저장하지 않음
                AnalysisSession.objects.create(
                    session_id=str(uuid.uuid4()),
                    original_filename=file.name,
                    file_path=save_path,
                    file_type=os.path.splitext(file.name)[-1][1:].upper(),
                    analysis_result=analysis_result,
                )
                print("DB 저장 완료")
                return redirect("web:dashboard")
            except Exception as e:
                print(f"업로드 중 오류: {e}")
                return render(request, "web/upload.html", {"form": form, "error": str(e)})
        else:
            print("폼이 유효하지 않음:", form.errors)
    else:
        form = UploadFileForm()
    return render(request, "web/upload.html", {"form": form})

def preview_columns(request):
    """
    업로드된 파일에서 칼럼명과 데이터 미리보기(2줄) 반환
    """
    if request.method == "POST" and request.FILES.get("file"):
        file = request.FILES["file"]
        try:
            # 여러 인코딩 시도
            for enc in ["utf-8", "cp949", "euc-kr", "latin1"]:
                try:
                    df = pd.read_csv(file, nrows=2, encoding=enc)
                    break
                except UnicodeDecodeError:
                    file.seek(0)  # 파일 포인터 리셋
            else:
                return JsonResponse({"error": "지원하지 않는 파일 인코딩입니다."}, status=400)
            columns = list(df.columns)
            preview = df.head(2).to_dict(orient="records")
            return JsonResponse({"columns": columns, "preview": preview})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"error": "No file uploaded"}, status=400)

def detect_anomalies_view(request):
    try:
        if request.method == "POST":
            file = request.FILES["file"]
            exclude_columns = request.POST.get("exclude_columns", "")
            exclude_columns = [col.strip() for col in exclude_columns.split(",") if col.strip()]
            user_col = request.POST.get("user_col")
            time_col = request.POST.get("time_col")
            file_path = save_uploaded_file(file)

            # 타임아웃 설정 (10분)
            timeout = 600  # 초 단위
            
            # 결과 변수 및 에러 플래그
            result = None
            analysis_error = False
            
            def run_analysis():
                nonlocal result, analysis_error
                try:
                    result = detect_anomalies(file_path, exclude_columns, user_col=user_col, time_col=time_col)
                except Exception as e:
                    analysis_error = True
                    print(f"분석 중 오류 발생: {e}")
            
            # 분석 쓰레드 시작
            analysis_thread = threading.Thread(target=run_analysis)
            analysis_thread.start()
            
            # 지정된 시간만큼 대기
            analysis_thread.join(timeout)
            
            # 타임아웃 발생 시
            if analysis_thread.is_alive() or analysis_error:
                return JsonResponse({
                    'success': False, 
                    'error': '처리할 수 없는 데이터셋입니다. 10분 이상 소요되었습니다.'
                }, status=408)  # 408 Request Timeout

            # === 그래프 HTML 생성 및 저장 ===
            from .visualize_graph import plot_anomaly_by_hour, plot_anomaly_by_user, plot_anomaly_score_distribution
            result_csv_path = result.get("result_csv_path")  # 분석 결과 파일 경로
            df_result = pd.read_csv(result_csv_path)         # 분석 결과 DataFrame (Anomaly 컬럼 포함)
            
            # 이상 로그만 필터링해서 그래프 생성
            user_graph_html = plot_anomaly_by_user(df_result, user_col) if user_col and user_col in df_result.columns else None
            hour_graph_html = plot_anomaly_by_hour(df_result, user_col, time_col) if user_col and time_col and user_col in df_result.columns and time_col in df_result.columns else None
            score_graph_html = plot_anomaly_score_distribution(df_result)

#            print("df.columns:", df.columns.tolist())
#            print("user_col:", user_col)
#            print("time_col:", time_col)
#            print("user_graph_html:", user_graph_html)
#            print("hour_graph_html:", hour_graph_html)
#            print("score_graph_html:", score_graph_html)

            AnalysisSession.objects.create(
                session_id=str(uuid.uuid4()),
                original_filename=file.name,
                file_path=file_path,
                file_type=os.path.splitext(file.name)[-1][1:].upper(),
                analysis_result=result,
                user_col=user_col,
                time_col=time_col,
                user_graph_html=user_graph_html,
                hour_graph_html=hour_graph_html,
                score_graph_html=score_graph_html,
            )
            return JsonResponse(result)
        
        return JsonResponse({"error": "Invalid request"}, status=400)
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({"error": str(e)}, status=500)

@require_http_methods(["GET"])
def upload_filter_view(request):
    return render(request, "web/upload_filter.html")

def save_uploaded_file(file):
    upload_dir = os.path.join(settings.MEDIA_ROOT, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.name)
    with open(file_path, "wb+") as destination:
        for chunk in file.chunks():
            destination.write(chunk)
    return file_path

@require_http_methods(["GET"])
def download_analysis_csv(request, session_id):
    session = get_object_or_404(AnalysisSession, session_id=session_id)
    result = session.analysis_result or {}

    download_type = request.GET.get("type", "anomaly")
    if download_type == "all":
        records = result.get("all_records", [])
    else:
        records = result.get("records", [])

    if not records:
        return HttpResponse("다운로드할 데이터가 없습니다.", status=404)

    df = pd.DataFrame(records)
    # 한글 깨짐 방지: utf-8-sig로 저장
    csv_data = df.to_csv(index=False, encoding="utf-8-sig")
    # 파일명에서 .csv 중복 제거
    base_name = session.original_filename
    if base_name.lower().endswith('.csv'):
        base_name = base_name[:-4]
    filename = f"{base_name}_{'전체' if download_type == 'all' else '이상치'}.csv"
    response = HttpResponse(csv_data, content_type="text/csv; charset=utf-8-sig")
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

def visualize_graph_view(request):
    if request.method == "POST":
        file = request.FILES["file"]
        user_col = request.POST.get("user_col")
        time_col = request.POST.get("time_col")
        file_path = save_uploaded_file(file)
        df = pd.read_csv(file_path)
        hour_html = plot_anomaly_by_hour(df, user_col, time_col)
        user_html = plot_anomaly_by_user(df, user_col)
        score_html = plot_anomaly_score_distribution(df)

        context = {
            'hour_graph': hour_html,
            'user_graph': user_html,
            'score_graph': score_html,
        }
        return render(request, 'web/dashboard.html', context)
    return JsonResponse({"error": "Invalid request"}, status=400)


#get_shap_plot 함수를 선언하여 SHAP그래프를 생성 및 이미지 파일 만듦. 그래프 모양, 크기를 여기서 바꿀 수 있음
import pandas as pd
import numpy as np
import shap
import matplotlib
import matplotlib.pyplot as plt
from django.http import JsonResponse
from io import BytesIO
import base64
from django.shortcuts import get_object_or_404
from .models import AnalysisSession
import platform

# ✅ 한글 폰트 설정 (윈도우 기준 예시)
matplotlib.rc('font', family='Malgun Gothic')  # 윈도우용
matplotlib.rcParams['axes.unicode_minus'] = False  # 마이너스 기호 깨짐 방지
matplotlib.use('Agg')

if platform.system() == 'Windows':
    matplotlib.rc('font', family='Malgun Gothic')
else:
    matplotlib.rc('font', family='AppleGothic')

def get_shap_plot(request, session_id, row_index):
    session = get_object_or_404(AnalysisSession, session_id=session_id)
    
    # 원본 데이터 로드 (실제 칼럼 확인용)
    try:
        original_df = pd.read_csv(session.file_path)
        original_columns = set(original_df.columns)
    except (FileNotFoundError, pd.errors.EmptyDataError, pd.errors.ParserError):
        original_df = None
        original_columns = set()
    
    # 데이터 불러오기
    X = pd.read_csv(session.file_path.replace(".csv", "_X_for_shap.csv"))
    shap_values = np.load(session.file_path.replace(".csv", "_shap_values.npy"))
    feature_cols = X.columns.tolist()
    
    # TF-IDF 칼럼 식별
    tfidf_cols = [col for col in feature_cols if '_tfidf_' in col]
    
    # TF-IDF 피처 원본 칼럼 찾기 - 원본 데이터셋 참고
    tfidf_mappings = {}
    lower_original_columns = {col.lower() for col in original_columns}
    for col in tfidf_cols:
        source_col = col.split('_tfidf_')[0]
        if source_col.lower() in lower_original_columns:
            # 실제 원본 컬럼명으로 표시
            matched_col = [col for col in original_columns if col.lower() == source_col.lower()][0]
            display_name = f"{matched_col}"
        else:
            display_name = f"added({source_col})"
        if display_name not in tfidf_mappings:
            tfidf_mappings[display_name] = []
        tfidf_mappings[display_name].append(col)

    # SHAP 값 계산
    row = shap_values[int(row_index)]
    shap_df = pd.DataFrame({
        'feature': feature_cols,
        'shap_value': row,
        'abs_val': np.abs(row),
        'data': X.iloc[int(row_index)].values
    })
    
    # TF-IDF 칼럼을 원본 칼럼으로 통합
    merged_shap_df = []

    # 원본 텍스트 칼럼에 대한 모든 TF-IDF 피처의 영향도 합치기
    for source_col, related_tfidf in tfidf_mappings.items():
        tfidf_rows = shap_df[shap_df['feature'].isin(related_tfidf)]
        total_shap = tfidf_rows['shap_value'].sum()
        
        # 원본 텍스트 칼럼이 있는 경우, 해당 칼럼의 고유값 개수나 길이로 다양성 측정
        if original_df is not None and source_col in original_df.columns:
            original_value = str(original_df[source_col].iloc[int(row_index)])
            # 텍스트 길이나 고유성을 기반으로 한 메트릭 사용
            unique_values = original_df[source_col].nunique()
            current_frequency = (original_df[source_col] == original_value).sum()
            # 희귀도 계산: 전체 개수 대비 현재 값의 빈도
            data_value = 1 - (current_frequency / len(original_df))
        else:
            # 여러 TF-IDF 피처의 data(스케일링 값) 중 가장 크게 벗어난 값 사용
            if not tfidf_rows.empty:
                # Weighted average of 'data' values using absolute SHAP values as weights
                data_value = np.average(tfidf_rows['data'], weights=tfidf_rows['abs_val'])
            else:
                data_value = 0
        
        merged_shap_df.append({
            'feature': f"{source_col}",  # tf-idf 피처를 원본 텍스트 칼럼으로 표시
            'shap_value': total_shap,
            'abs_val': abs(total_shap),
            'data': data_value
        })

    # 나머지 non-TF-IDF 피처 추가
    # 모든 TF-IDF 피처(flatten) 리스트 생성
    all_tfidf_features = [item for sublist in tfidf_mappings.values() for item in sublist]
    non_tfidf_features = [f for f in feature_cols if f not in all_tfidf_features]
    for feature in non_tfidf_features:
        idx = feature_cols.index(feature)
        
        # 원본 데이터에서 해당 특성의 값 가져오기 (가능한 경우)
        if original_df is not None and feature in original_df.columns:
            original_value = original_df[feature].iloc[int(row_index)]
            # 숫자형 데이터의 경우 평균과의 차이 계산
            if pd.api.types.is_numeric_dtype(original_df[feature]):
                mean_value = original_df[feature].mean()
                data_value = abs(original_value - mean_value)
            else:
                # 범주형 데이터의 경우 스케일링된 값 사용
                data_value = abs(X[feature].iloc[int(row_index)])
        else:
            # 원본 데이터에 없는 경우 스케일링된 값 사용
            data_value = abs(X[feature].iloc[int(row_index)])
        
        merged_shap_df.append({
            'feature': feature,
            'shap_value': row[idx],
            'abs_val': abs(row[idx]),
            'data': data_value
        })

    # DataFrame으로 변환
    merged_shap_df = pd.DataFrame(merged_shap_df)
    
    # SHAP < 0인 feature 중 영향 큰 순서대로 정렬
    negative_df = merged_shap_df[merged_shap_df['shap_value'] < 0].sort_values(by='abs_val', ascending=False).reset_index(drop=True)
    # 무조건 6개로 고정되게 리인덱싱 (부족하면 빈 bar로)
    negative_df = negative_df.reindex(range(6)).fillna({
        'feature': '', 'shap_value': 0, 'abs_val': 0, 'data': 0
    })
    max_len = 6  # 항상 bar 6개로 고정


    y_pos = np.arange(max_len)
    fig, ax = plt.subplots(figsize=(6, max(8, max_len * 1.5)))


    # SHAP 값을 절댓값으로 바꿔 오른쪽으로 표시
    flipped_values = -negative_df['shap_value']  # → 양수로 변환
    ax.set_xlim(0, flipped_values.max() * 1.2)

    ax.barh(y_pos, flipped_values, color='salmon', label='이상치 기여도', align='center', height = 0.5)
    ax.axvline(x=0, color='black', linewidth=1)

    ax.grid(axis='y', visible=False)  # 가로줄 제거
    ax.grid(axis='x', visible=True, linestyle='--', alpha=0.8)  # 세로줄은 표시 (옵션)


    ax.set_yticks(y_pos)
    ax.set_yticklabels([''] * max_len)
    ax.invert_yaxis()

    for i, label in enumerate(negative_df['feature']):
        if label:
            ax.text(flipped_values[i] + flipped_values.max() * 0.02, i, label, ha='left', va='center', fontsize=10, fontweight='bold')

    ax.set_title(f"{row_index}번 ROW\n", fontweight='bold')
    ax.set_xlabel("영향도 크기 (SHAP)")
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.1), frameon=False)

    plt.tight_layout()
    plt.subplots_adjust(bottom=0.15)

    # base64 인코딩
    buffer = BytesIO()
    fig.savefig(buffer, format="png")
    buffer.seek(0)
    image_png = buffer.getvalue()
    buffer.close()
    encoded = base64.b64encode(image_png).decode('utf-8')
    img_html = f'<img src="data:image/png;base64,{encoded}" style="width:100%;">'

    explanation_text = generate_shap_explanation(negative_df)  #SHAP 줄글 설명용

    # 그래프 아래 설명용 문단
    middle_html = """
    <div style='margin: 1rem 0; color: #666; font-size: 0.95em;'>
        이 그래프는 AI가 해당 로그를 이상으로 판단하는 데 영향을 준 항목들을 기여도 순으로 보여줍니다.
    </div>
    """
    description_html = ""
    if hasattr(session, 'analysis_result') and session.analysis_result:
        description_html = session.analysis_result.get('text_html', '')

    return JsonResponse({
        'success': True,
        'plot_html': img_html,
        'shap_middle_html': middle_html,
        'shap_explanation': explanation_text,
        'description_html': description_html 

})


#SHAP 그래프에 대한 줄글 설명 출력 코드
def generate_shap_explanation(shap_row_df):
    explanations = []
    for _, row in shap_row_df.iterrows():
        feature = row['feature']
        if not feature:  # feature가 비어 있는 경우 (빈 bar용) 설명 제외
            continue

        # SHAP 값의 절댓값을 기준으로 영향도 판단
        shap_magnitude = abs(row['shap_value'])
        data_value = row['data']
        
        # 만약 data_value가 Series나 배열이면 float로 변환 (대표값 사용)
        if isinstance(data_value, (np.ndarray, pd.Series)):
            data_magnitude = float(np.abs(data_value).max())
        else:
            data_magnitude = abs(float(data_value)) if data_value is not None else 0.0

        # SHAP 값의 크기에 따른 영향도 레벨 결정
        if shap_magnitude > 0.1:
            level = "<span style='color: #B22222'>크게</span>"  # 빨간색
        elif shap_magnitude > 0.05:
            level = "<span style='color: #e67e22'>중간 정도</span>"  # 주황색
        elif shap_magnitude > 0.01:
            level = "<span style='color: #f1c40f'>약간</span>"  # 노란색
        else:
            level = "거의"

        # 설명 텍스트 생성 - SHAP 기여도를 중심으로
        if shap_magnitude < 0.01:
            explanations.append(
                f"{feature}: 이상 탐지에 거의 영향 없음 (기여도: {shap_magnitude:.3f})"
            )
        else:
            # 데이터 차이와 영향도의 관계 설명
            if data_magnitude < 0.01 and shap_magnitude > 0.05:
                # 값 차이는 작지만 영향이 큰 경우
                explanation_reason = "※ 이 특성은 희귀하거나 모델이 중요하게 학습한 패턴입니다"
                data_text = "값의 차이는 미미하지만"
            elif data_magnitude < 0.01:
                data_text = "값의 차이는 미미하며"
                explanation_reason = ""
            elif data_magnitude < 1.0:
                data_text = f"평균 대비 {data_magnitude:.2f} 차이로"
                explanation_reason = ""
            else:
                data_text = f"평균 대비 {data_magnitude:.2f} 만큼 크게 차이나며"
                explanation_reason = ""
            
            base_explanation = f"{feature}: {data_text} 이상 탐지에 {level} 영향 (기여도: {shap_magnitude:.3f})"
            if explanation_reason:
                explanations.append(f"{base_explanation}<br><small style='color: #666; font-style: italic;'>{explanation_reason}</small>")
            else:
                explanations.append(base_explanation)

    explanations.append("<span style='color: #555; font-size: 0.95em;'>💡 <strong>참고:</strong> 값의 차이가 작아도 영향이 클 수 있습니다. 이는 해당 특성이 희귀하거나, 모델이 이상 탐지의 중요한 패턴으로 학습했기 때문입니다.</span>")

    return explanations

@csrf_exempt
@require_http_methods(["DELETE"])
def delete_all_analysis_sessions(request):
    """모든 분석 세션 삭제"""
    AnalysisSession.objects.all().delete()
    return JsonResponse({"success": True})

