from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from .forms import UploadFileForm
from .models import AnalysisSession, AnomalyLog
import uuid
import json
import os
from django.conf import settings
import pandas as pd
from .ai_script import detect_anomalies
from .visualize_graph import plot_anomaly_by_hour, plot_anomaly_by_user, plot_anomaly_score_distribution
from django.db.models import Count, Q
from django.contrib.auth.models import User

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
                'created_at': session.created_at.strftime('%Y-%m-%d %H:%M'),
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
                'created_at': session.created_at.strftime('%Y-%m-%d %H:%M:%S'),
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
            result = detect_anomalies(file_path, exclude_columns, user_col=user_col, time_col=time_col)
            result_csv_path = result.get("result_csv_path")
            df_result = pd.read_csv(result_csv_path)

            # === 이상 로그 저장 및 디버깅 === 
            if user_col and "Anomaly" in df_result.columns:
                print("user_col:", user_col)
                print("df_result.columns:", df_result.columns.tolist())
                print("Anomaly 값 종류:", df_result["Anomaly"].unique())
                anomalies = df_result[df_result["Anomaly"].astype(str).isin(["1", "1.0", "True", "true"])]
                print("이상치 개수:", len(anomalies))
                print("기존 AnomalyLog 삭제 중...")
                AnomalyLog.objects.all().delete()  # 기존 로그 모두 삭제
                
                for _, row in anomalies.iterrows():
                    username = row[user_col]
                    print("저장할 username:", username)
                    try:
                        user = User.objects.get(username=username)
                    except User.DoesNotExist:
                        user = User.objects.create_user(username=username, password="changeme")
                    log_data = row.to_json(force_ascii=False)
                    AnomalyLog.objects.create(user=user, log_data=log_data)

            # === 그래프 HTML 생성 및 저장 ===
            user_graph_html = plot_anomaly_by_user(df_result, user_col) if user_col and user_col in df_result.columns else None
            hour_graph_html = plot_anomaly_by_hour(df_result, user_col, time_col) if user_col and time_col and user_col in df_result.columns and time_col in df_result.columns else None
            score_graph_html = plot_anomaly_score_distribution(df_result)

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
        return JsonResponse({"error": str(e)},status=500)

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

# 한글 폰트 설정 (윈도우 기준 예시)
matplotlib.rc('font', family='Malgun Gothic')  # 윈도우용
matplotlib.rcParams['axes.unicode_minus'] = False  # 마이너스 기호 깨짐 방지
matplotlib.use('Agg')

if platform.system() == 'Windows':
    matplotlib.rc('font', family='Malgun Gothic')
else:
    matplotlib.rc('font', family='AppleGothic')

def get_shap_plot(request, session_id, row_index):
    session = get_object_or_404(AnalysisSession, session_id=session_id)

    # 데이터 불러오기 (ai_script.py 함수에서 추출해낸 두 개의 파일 가져옴)
    X = pd.read_csv(session.file_path.replace(".csv", "_X_for_shap.csv"))
    shap_values = np.load(session.file_path.replace(".csv", "_shap_values.npy"))
    feature_cols = X.columns.tolist()

    # 해당 샘플의 SHAP 값 가져오기
    row = shap_values[int(row_index)]
    shap_df = pd.DataFrame({
        'feature': feature_cols,
        'shap_value': row,
        'abs_val': np.abs(row),
        'data': X.iloc[int(row_index)].values  # SHAP 줄글 설명
    })

    # SHAP < 0인 feature 중 영향 큰 순서대로 정렬
    negative_df = shap_df[shap_df['shap_value'] < 0].sort_values(by='abs_val', ascending=False).reset_index(drop=True)
    # 무조건 6개로 고정되게 리인덱싱 (부족하면 빈 bar로)
    negative_df = negative_df.reindex(range(6)).fillna({
        'feature': '', 'shap_value': 0, 'abs_val': 0, 'data': 0
    })
    max_len = 6  


    y_pos = np.arange(max_len)
    fig, ax = plt.subplots(figsize=(6, max(8, max_len * 1.5)))


    # SHAP 값을 절댓값으로 바꿔 오른쪽으로 표시
    flipped_values = -negative_df['shap_value']  
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

        value = row['data']  # 스케일링된 값 (평균 0, std 1 기준)
        magnitude = abs(value)

        if magnitude > 2:
            level = "<span style='color: #B22222'>매우 크게</span>"  # 빨간색
        elif magnitude > 1:
            level = "<span style='color: #e67e22'>크게</span>"  # 주황색
        elif magnitude > 0.5:
            level = "<span style='color: #f1c40f'>약간</span>"  # 노란색
        else:
            level = ""

        explanations.append(
            f"{feature} 값은 평균치보다 {magnitude:.2f}만큼 {level} 벗어났습니다"
        )

    explanations.append("<span style='color: #555; font-size: 0.95em;'>평균과 많이 달라도 탐지 결과에는 영향이 적을 수 있고, 조금 달라도 비교적 큰 영향을 줄 수 있습니다.</span>")

    return explanations

@csrf_exempt
@require_http_methods(["DELETE"])
def delete_all_analysis_sessions(request):
    """모든 분석 세션 삭제"""
    AnalysisSession.objects.all().delete()
    return JsonResponse({"success": True})


from django.shortcuts import get_object_or_404
from .models import AnomalyLog  

def user_anomaly_count(request, username):
    """
    사용자명을 입력받아 해당 사용자가 발생시킨 이상 로그 건수를 반환합니다.
    """
    try:
        # 먼저 해당 사용자가 실제로 존재하는지 확인
        user = User.objects.get(username=username)
        count = AnomalyLog.objects.filter(user=user).count()
        return JsonResponse({'username': username, 'anomaly_count': count})
    except User.DoesNotExist:
        return JsonResponse({'error': '정확한 사용자명을 입력해주세요.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def top_anomaly_users(request, top_n):
    """
    숫자를 입력받아 이상 로그를 많이 발생시킨 상위 N명의 사용자와 로그 건수를 반환합니다.
    """
    try:
        top_users = (
            AnomalyLog.objects.values('user__username')
            .annotate(count=Count('id'))
            .order_by('-count')[:top_n]
        )
        formatted_users = [{'username': user['user__username'], 'anomaly_count': user['count']} for user in top_users]
        return JsonResponse({'top_users': formatted_users})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@require_http_methods(["GET"])
def search_anomaly_logs(request):
    """
    특정 사용자의 이상 로그 건수를 검색합니다.
    """
    query = request.GET.get('username', '')  # GET 요청에서 'username' 파라미터 가져오기
    if query:
        # 먼저 해당 사용자가 실제로 존재하는지 확인
        try:
            user = User.objects.get(username=query)  # 정확한 사용자명으로 검색
            results = AnomalyLog.objects.filter(user=user)  # 해당 사용자의 이상 로그 검색
            count = results.count()  # 검색된 이상 로그 건수
            return JsonResponse({'username': query, 'anomaly_count': count})
        except User.DoesNotExist:
            return JsonResponse({'error': '정확한 사용자명을 입력해주세요.'}, status=404)
    else:
        return JsonResponse({'error': '검색어를 입력해주세요.'}, status=400)
from django.shortcuts import render


def anomaly_search_view(request):
    return render(request, 'web/viewall.html')



@require_http_methods(["GET"])
def get_user_graph(request):
    """
    사용자별 이상 로그 그래프를 반환하는 뷰 (viewall.html용)
    """
    try:
        latest_session = AnalysisSession.objects.filter(
            user_graph_html__isnull=False
        ).order_by('-created_at').first()
        
        if latest_session and latest_session.user_graph_html:
            user_graph_html = latest_session.user_graph_html

            # 그래프 시각 요소 조정 스크립트
            size_adjustment_script = """
            <script>
            document.addEventListener('DOMContentLoaded', function() {
                setTimeout(function() {
                    try {
                        var plotElement = document.querySelector('.plotly-graph-div');
                        if (plotElement && window.Plotly) {
                            var currentLayout = plotElement.layout || {};
                            
                            var newLayout = {
                                ...currentLayout,
                                height: 600,
                                font: {size: 16},
                                margin: {l: 60, r: 60, t: 80, b: 60},
                                title: {
                                    text: currentLayout.title?.text || 'Anomalies by User',
                                    font: {size: 20}
                                }
                            };
                            
                            Plotly.relayout(plotElement, newLayout);
                        }
                    } catch (e) {
                    }
                }, 500);
            });
            </script>
            """

            return HttpResponse(user_graph_html + size_adjustment_script)

        # user_graph_html이 없으면 아무것도 출력하지 않음
        return HttpResponse("")
    
    except Exception as e:
        print(f"get_user_graph 오류: {e}")
        return HttpResponse(f"""
            <div style="display: flex; align-items: center; justify-content: center; height: 400px; color: #dc3545;">
                <div style="text-align: center;">
                    <h3>그래프 로딩 오류</h3>
                    <p>그래프를 불러오는 중 오류가 발생했습니다.</p>
                    <small>{str(e)}</small>
                    <br><br>
                    <a href="/dashboard/" style="color: #007bff; text-decoration: none;">
                        대시보드로 돌아가기 →
                    </a>
                </div>
            </div>
        """)


    
def total_anomaly_count(request):
    """
    전체 이상 로그 건수를 반환합니다.
    """
    try:
        total_count = AnomalyLog.objects.count()
        return JsonResponse({'total_count': total_count})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)