from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .forms import UploadFileForm
from .models import AnalysisSession
import uuid
import json
import os
from django.conf import settings

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
                from .ai_script import detect_anomalies
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