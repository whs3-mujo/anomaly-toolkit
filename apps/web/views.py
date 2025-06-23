import os
import uuid

from django.conf import settings
from django.shortcuts import render, redirect
from django.http import JsonResponse

from .forms import UploadFileForm
from ai_script import detect_anomalies


def save_to_media(uploaded_file):
    """
    MEDIA_ROOT 아래에 uuid_파일명 으로 저장하고
    저장된 파일 경로를 반환.
    """
    upload_dir = settings.MEDIA_ROOT
    os.makedirs(upload_dir, exist_ok=True)

    filename = f"{uuid.uuid4().hex}_{uploaded_file.name}"
    file_path = os.path.join(upload_dir, filename)

    with open(file_path, 'wb+') as dest:
        for chunk in uploaded_file.chunks():
            dest.write(chunk)

    return file_path


def upload_view(request):
    """
    1) 업로드 폼 보여주기
    2) POST 시 파일 저장 → 가짜 task_id 생성 → Progress 페이지로 리다이렉트
    """
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            path = save_to_media(form.cleaned_data['datafile'])
            task_id = uuid.uuid4()  # 실제론 Celery task id 등
            # TODO: 여기에 detect_anomalies를 비동기로 실행하도록 연결
            return redirect('progress', task_id=task_id)
    else:
        form = UploadFileForm()

    return render(request, 'web/upload.html', { 'form': form })


def progress_view(request, task_id):
    """
    클라이언트에서 JS 폴링으로 호출할 JSON API.
    실제 progress 정보는 Celery나 DB에서 조회하게 구현하세요.
    """
    # TODO: 실제 진행률 로직 연결
    fake_progress = 45  # 임시: 0~100 사이 숫자
    status = 'Processing' if fake_progress < 100 else 'Complete'
    return JsonResponse({
        'task_id': str(task_id),
        'progress': fake_progress,
        'status': status,
    })


def dashboard_view(request):
    """
    대시보드 페이지 (현재는 빈 틀)
    이후 ai 결과를 가공해서 context에 담아주세요.
    """
    return render(request, 'web/dashboard.html', {})
