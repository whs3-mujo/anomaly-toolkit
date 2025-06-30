# from django.db import models
# import uuid

# class ChatSession(models.Model):
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     title = models.CharField(max_length=100)
#     created_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return self.title

# class Message(models.Model):
#     session = models.ForeignKey(ChatSession, related_name='messages', on_delete=models.CASCADE)
#     content = models.TextField()
#     is_user = models.BooleanField(default=True)
#     timestamp = models.DateTimeField(auto_now_add=True)

# class Session(models.Model):
#     name = models.CharField(max_length=255)
#     created_at = models.DateTimeField(auto_now_add=True)
#     log_file = models.FileField(upload_to='logs/')

# apps/web/models.py 또는 해당하는 models.py 파일에 추가

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import json

class AnalysisSession(models.Model):
    """분석 세션 모델"""
    
    # 세션 상태 선택지
    STATUS_CHOICES = [
        ('pending', '분석 중'),
        ('completed', '완료'),
        ('failed', '실패'),
    ]
    
    # 기본 정보
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)  # 사용자 (로그인한 경우)
    session_id = models.CharField(max_length=100, unique=True)  # 세션 고유 ID
    
    # 파일 정보
    original_filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    file_size = models.IntegerField()
    file_type = models.CharField(max_length=50)
    
    # 분석 정보
    analysis_type = models.CharField(max_length=100, default='general')  # 분석 타입
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # 결과 데이터 (JSON 형태로 저장)
    analysis_result = models.JSONField(default=dict, blank=True)
    
    # 메타데이터
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = '분석 세션'
        verbose_name_plural = '분석 세션들'
    
    def __str__(self):
        return f"{self.original_filename} - {self.get_status_display()}"
    
    def get_short_filename(self, max_length=20):
        """파일명을 짧게 표시"""
        if len(self.original_filename) <= max_length:
            return self.original_filename
        return self.original_filename[:max_length-3] + "..."
    
    def get_file_size_display(self):
        """파일 크기를 읽기 쉽게 표시"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def set_completed(self, result_data):
        """분석 완료 처리"""
        self.status = 'completed'
        self.analysis_result = result_data
        self.completed_at = timezone.now()
        self.save()
    
    def set_failed(self, error_message=""):
        """분석 실패 처리"""
        self.status = 'failed'
        self.analysis_result = {'error': error_message}
        self.save()


class AnalysisHistory(models.Model):
    """분석 히스토리 상세 정보 (필요시 사용)"""
    
    session = models.ForeignKey(AnalysisSession, on_delete=models.CASCADE, related_name='history')
    step = models.CharField(max_length=100)  # 분석 단계
    message = models.TextField()  # 단계별 메시지
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['timestamp']
        
    def __str__(self):
        return f"{self.session.session_id} - {self.step}"