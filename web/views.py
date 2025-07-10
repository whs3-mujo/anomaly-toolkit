from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .forms import UploadFileForm
from .models import AnalysisSession
import uuid
import json
import os
from django.conf import settings
import pandas as pd
from .ai_script import detect_anomalies

def redirect_dashboard(request):
    return redirect('web:dashboard')

def dashboard_view(request):
    return render(request, 'web/dashboard.html')


def get_analysis_history(request):
    """분석 히스토리 목록 반환"""
    try:
        sessions = AnalysisSession.objects.all().order_by('-created_at')
        
        # JSON 형태로 변환
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
    
    # 분석 세션 생성 (완료된 결과와 함께)
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
        
        # 새 파일명 받기
        data = json.loads(request.body)
        new_filename = data.get('filename', '').strip()
        
        if not new_filename:
            return JsonResponse({'success': False, 'error': '파일명을 입력해주세요.'}, status=400)
        
        # 파일명 업데이트
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
                # 파일 저장
                save_dir = os.path.join(settings.MEDIA_ROOT, "uploads")
                os.makedirs(save_dir, exist_ok=True)
                save_path = os.path.join(save_dir, file.name)
                with open(save_path, "wb+") as dest:
                    for chunk in file.chunks():
                        dest.write(chunk)
                print(f"파일 저장 완료: {save_path}")

                # 이상 탐지
                analysis_result = detect_anomalies(save_path)
                print(f"분석 결과: {analysis_result}")

                # DB 저장
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
        df = pd.read_csv(file, nrows=2)
        columns = list(df.columns)
        preview = df.head(2).to_dict(orient="records")
        return JsonResponse({"columns": columns, "preview": preview})
    return JsonResponse({"error": "No file uploaded"}, status=400)

def detect_anomalies_view(request):
    try:
        if request.method == "POST":
            file = request.FILES["file"]
            exclude_columns = request.POST.get("exclude_columns", "")
            exclude_columns = [col.strip() for col in exclude_columns.split(",") if col.strip()]
            file_path = save_uploaded_file(file)
            result = detect_anomalies(file_path, exclude_columns)
            # DB 저장 추가
            AnalysisSession.objects.create(
                session_id=str(uuid.uuid4()),
                original_filename=file.name,
                file_path=file_path,
                file_type=os.path.splitext(file.name)[-1][1:].upper(),
                analysis_result=result,
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
    """분석 결과(이상치만) CSV 다운로드"""
    session = get_object_or_404(AnalysisSession, session_id=session_id)
    result = session.analysis_result or {}

    # JSON 목록(records) 가져오기
    records = result.get("records", [])
    if not records:
        return HttpResponse("이상치 레코드가 없습니다.", status=404)

    try:
        # JSON → DataFrame → CSV
        df = pd.DataFrame(records)
        csv_data = df.to_csv(index=False, encoding="utf-8-sig")

        response = HttpResponse(csv_data, content_type="text/csv")
        response['Content-Disposition'] = (
            f'attachment; filename="{session.original_filename}.csv"'
        )
        return response

    except Exception as e:
        return HttpResponse(f"CSV 생성 중 오류: {e}", status=500)
    
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

# ✅ 한글 폰트 설정 (윈도우 기준 예시)
matplotlib.rc('font', family='Malgun Gothic')  # 윈도우용
matplotlib.rcParams['axes.unicode_minus'] = False  # 마이너스 기호 깨짐 방지


def get_shap_plot(request, session_id, row_index):
    session = get_object_or_404(AnalysisSession, session_id=session_id)

    # 데이터 불러오기
    X = pd.read_csv(session.file_path.replace(".csv", "_X_for_shap.csv"))
    shap_values = np.load(session.file_path.replace(".csv", "_shap_values.npy"))
    feature_cols = X.columns.tolist()

    # 해당 샘플의 SHAP 값 가져오기
    row = shap_values[int(row_index)]
    shap_df = pd.DataFrame({
        'feature': feature_cols,
        'shap_value': row,
        'abs_val': np.abs(row)
    })

    # SHAP < 0인 이상치 기여 feature만 추출
    negative_df = shap_df[shap_df['shap_value'] < 0].sort_values(by='abs_val', ascending=False).reset_index(drop=True)
    max_len = max(len(negative_df), 5)
    negative_df = negative_df.reindex(range(max_len)).fillna({'feature': '', 'shap_value': 0})

    y_pos = np.arange(max_len)
    fig, ax = plt.subplots(figsize=(6, max(8, max_len * 1.5)))


    # SHAP 값을 절댓값으로 바꿔 오른쪽으로 표시
    flipped_values = -negative_df['shap_value']  # → 양수로 변환
    ax.set_xlim(0, flipped_values.max() * 1.2)

    ax.barh(y_pos, flipped_values, color='salmon', label='이상치 기여', align='center')
    ax.axvline(x=0, color='black', linewidth=1)

    ax.grid(axis='y', visible=False)  # 가로줄 제거
    ax.grid(axis='x', visible=True, linestyle='--', alpha=0.8)  # 세로줄 표시 (옵션)


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

    return JsonResponse({'success': True, 'plot_html': img_html})
