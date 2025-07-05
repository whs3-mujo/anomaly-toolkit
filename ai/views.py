# apps/ai/views.py

import os
import uuid
from django.conf import settings
from django.shortcuts import render
from .forms import UploadFileForm
from .ai_script import detect_anomalies

def save_to_media(uploaded_file):
    """
    UploadedFile 객체를 MEDIA_ROOT 아래에 저장하고,
    저장된 파일의 전체 경로를 반환
    """
    # UUID를 붙여 충돌 방지
    filename = f"{uuid.uuid4().hex}_{uploaded_file.name}"
    upload_dir = settings.MEDIA_ROOT
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, filename)
    with open(file_path, 'wb+') as dest:
        for chunk in uploaded_file.chunks():
            dest.write(chunk)

    return file_path

def ai_home(request):
    result_html = None

    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded = form.cleaned_data['datafile']
            path = save_to_media(uploaded)
            result_html = detect_anomalies(path)
    else:
        form = UploadFileForm()

    return render(request, 'ai/home.html', {
        'form': form,
        'result': result_html,
    })