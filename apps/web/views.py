from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.contrib.sessions.models import Session
from .models import AnalysisSession, AnalysisHistory
import uuid
import json

def dashboard_view(request):
    """대시보드 메인 뷰"""
    return render(request, 'web/dashboard.html')


@require_http_methods(["GET"])
def get_analysis_history(request):
    """AJAX로 분석 히스토리 목록 반환"""
    try:
        # 현재는 모든 세션을 가져오도록 수정 (테스트용)
        # 나중에 사용자별로 필터링 로직 추가
        sessions = AnalysisSession.objects.all().order_by('-created_at')
        
        # JSON 형태로 변환
        history_data = []
        for session in sessions:
            history_data.append({
                'id': session.id,
                'session_id': session.session_id,
                'filename': session.get_short_filename(),
                'full_filename': session.original_filename,
                'status': session.status,
                'status_display': session.get_status_display(),
                'file_size': session.get_file_size_display(),
                'file_type': session.file_type,
                'created_at': session.created_at.strftime('%Y-%m-%d %H:%M'),
                'has_result': bool(session.analysis_result and session.status == 'completed'),
            })
        
        return JsonResponse({
            'success': True,
            'history': history_data,
            'total': len(history_data)
        })
        
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()  # 디버깅용
        }, status=500)


@require_http_methods(["GET"])
def get_analysis_detail(request, session_id):
    """특정 분석 결과 상세 정보 반환"""
    try:
        # 현재는 모든 세션 접근 가능하도록 수정 (테스트용)
        session = get_object_or_404(AnalysisSession, session_id=session_id)
        
        # 분석 결과 반환
        return JsonResponse({
            'success': True,
            'session': {
                'id': session.id,
                'session_id': session.session_id,
                'filename': session.original_filename,
                'file_size': session.get_file_size_display(),
                'file_type': session.file_type,
                'status': session.status,
                'status_display': session.get_status_display(),
                'created_at': session.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'completed_at': session.completed_at.strftime('%Y-%m-%d %H:%M:%S') if session.completed_at else None,
                'analysis_result': session.analysis_result,
            }
        })
        
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()  # 디버깅용
        }, status=500)


def create_analysis_session(request, filename, file_path, file_size, file_type):
    """새로운 분석 세션 생성 (다른 뷰에서 호출용)"""
    session_id = str(uuid.uuid4())
    
    # 분석 세션 생성
    analysis_session = AnalysisSession.objects.create(
        user=request.user if request.user.is_authenticated else None,
        session_id=session_id,
        original_filename=filename,
        file_path=file_path,
        file_size=file_size,
        file_type=file_type,
        status='pending'
    )
    
    # 비로그인 사용자의 경우 세션에 저장
    if not request.user.is_authenticated:
        if not request.session.session_key:
            request.session.create()
        
        session_analysis_ids = request.session.get('analysis_sessions', [])
        session_analysis_ids.append(session_id)
        request.session['analysis_sessions'] = session_analysis_ids
        request.session.modified = True
    
    return analysis_session


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_analysis_session(request, session_id):
    """분석 세션 삭제"""
    try:
        # 현재는 모든 세션 삭제 가능하도록 수정 (테스트용)
        session = get_object_or_404(AnalysisSession, session_id=session_id)
        
        # 세션 삭제
        session.delete()
        
        return JsonResponse({'success': True, 'message': '분석 기록이 삭제되었습니다.'})
        
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()  # 디버깅용
        }, status=500)
    
@csrf_exempt
@require_http_methods(["POST"])
def rename_analysis_session(request, session_id):
    """분석 세션 이름 변경"""
    try:
        # 현재는 모든 세션 이름 변경 가능하도록 수정 (테스트용)
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
        import traceback
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()  # 디버깅용
        }, status=500)