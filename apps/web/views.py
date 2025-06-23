# apps/web/views.py

from django.shortcuts import render
from .forms import UploadFileForm
from ai_script import detect_anomalies

def home(request):
    result_html = None
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded = form.cleaned_data['datafile']
            path = save_to_media(uploaded)   # 기존에 구현한 파일 저장 로직
            result_html = detect_anomalies(path)

    else:
        form = UploadFileForm()

    return render(request, 'home.html', {
        'form': form,
        'result': result_html,
    })
