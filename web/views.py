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
    result = session.analysis_result
    # 이상치 표가 없으면 에러
    if not result or "table_html" not in result:
        return HttpResponse("No result", status=404)
    table_html = result["table_html"]
    if not table_html.strip().startswith("<table"):
        return HttpResponse("No anomaly table to download.", status=404)
    try:
        df = pd.read_html(table_html)[0]
        csv_data = df.to_csv(index=False, encoding="utf-8-sig")
        response = HttpResponse(csv_data, content_type="text/csv")
        response['Content-Disposition'] = f'attachment; filename="{session.original_filename}.csv"'
        return response
    except Exception as e:
        return HttpResponse(f"Error: {e}", status=500)