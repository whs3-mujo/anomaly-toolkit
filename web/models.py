# web/models.py

from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User  # 사용자 모델 사용

class AnalysisSession(models.Model):
    """분석 세션 모델 - 완료된 분석만 저장"""
    
    # 기본 정보
    session_id = models.CharField(max_length=100, unique=True)  # 세션 고유 ID
    
    # 파일 정보
    original_filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    file_type = models.CharField(max_length=50)
    
    # 결과 데이터 (JSON 형태로 저장)
    analysis_result = models.JSONField(default=dict, blank=True)
    
    # 메타데이터
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # 그래프 HTML 데이터
    user_graph_html = models.TextField(null=True, blank=True)
    hour_graph_html_top10 = models.TextField(null=True, blank=True)
    hour_graph_html_top3 = models.TextField(null=True, blank=True)
    score_graph_html = models.TextField(null=True, blank=True)
    
    # 컬럼 정보
    user_col = models.CharField(max_length=100, null=True, blank=True)
    time_col = models.CharField(max_length=100, null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = '분석 세션'
        verbose_name_plural = '분석 세션들'
    
    def __str__(self):
        return f"{self.original_filename}"
    
    def get_short_filename(self, max_length=20):
        if len(self.original_filename) <= max_length:
            return self.original_filename
        return self.original_filename[:max_length-3] + "..."

class AnomalyLog(models.Model):
    """이상 로그 모델 - 사용자별 이상 로그 데이터를 저장"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # 사용자와 연결
    log_data = models.TextField()  # 로그 데이터
    created_at = models.DateTimeField(auto_now_add=True)  # 생성 시간

    class Meta:
        ordering = ['-created_at']
        verbose_name = '이상 로그'
        verbose_name_plural = '이상 로그들'

    def __str__(self):
        return f"{self.user.username} - {self.created_at}"