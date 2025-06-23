# apps/web/views.py

from django.shortcuts import render

def home(request):
    # 프로젝트 최상단 templates/web/home.html 을 렌더
    return render(request, 'web/home.html')
