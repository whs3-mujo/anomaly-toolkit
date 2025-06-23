# apps/web/urls.py

from django.urls import path
from . import views

app_name = 'web'

urlpatterns = [
    path('upload/',   views.upload_view,   name='upload'),
    path('progress/<uuid:task_id>/', views.progress_view, name='progress'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
]
