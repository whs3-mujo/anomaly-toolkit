# apps/ai/views.py

from django.shortcuts import render

def dashboard(request):
    # dashboard.html 렌더
    return render(request, 'ai/dashboard.html')
