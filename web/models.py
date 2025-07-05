# web/models.py

from django.db import models
from django.utils import timezone

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
#    analysis_type = models.CharField(max_length=50, default='default_type')
    
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