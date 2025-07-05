# apps/web/urls.py

from django.urls import path
from . import views

app_name = 'web'

#urlpatterns = [
#    path('dashboard/', views.dashboard_view, name='dashboard'),
#    path('api/analysis/history/', views.get_analysis_history, name='api_analysis_history'),
#    path('api/analysis/detail/<str:session_id>/', views.get_analysis_detail, name='api_analysis_detail'),
#    path('api/analysis/delete/<str:session_id>/', views.delete_analysis_session, name='api_delete_session'),    
#    path('api/analysis/rename/<str:session_id>/', views.rename_analysis_session, name='api_rename_session'),
#]

urlpatterns = [
    path("", views.redirect_dashboard, name="root-redirect"),
    path("upload/", views.upload_view, name="upload"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("api/analysis/history/", views.get_analysis_history, name="analysis_history"),
    path("api/analysis/detail/<str:session_id>/", views.get_analysis_detail, name="analysis_detail"),
    path("api/analysis/delete/<str:session_id>/", views.delete_analysis_session, name="analysis_delete"),
    path("api/analysis/rename/<str:session_id>/", views.rename_analysis_session, name="analysis_rename"),
]
