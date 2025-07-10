# Django shell에서 실행할 테스트 데이터 생성 스크립트

from web.models import AnalysisSession
import uuid
from datetime import datetime, timedelta
from django.utils import timezone

# 기존 데이터 삭제 (필요시)
# AnalysisSession.objects.all().delete()

# 테스트 데이터 생성
test_data = [
    {
        'filename': 'HDFS_TEST.log',
        'file_type': 'LOG',
        'analysis_result': {
            'summary': 'HDFS 로그 분석 완료',
            'total_lines': 15420,
            'error_count': 23,
            'warning_count': 156,
            'anomalies': ['Disk space warning', 'Connection timeout']
        }
    },
    {
        'filename': 'TEST.log',
        'file_type': 'LOG', 
        'analysis_result': {
            'summary': '일반 로그 분석 완료',
            'total_lines': 8930,
            'error_count': 12,
            'warning_count': 89
        }
    },
    {
        'filename': 'apache2.csv',
        'file_type': 'CSV',
        'analysis_result': {
            'summary': 'Apache 액세스 로그 분석',
            'total_requests': 45672,
            'unique_ips': 1203,
            'status_codes': {'200': 42341, '404': 1892, '500': 439},
            'top_pages': ['/index.html', '/api/data', '/dashboard']
        }
    },
    {
        'filename': 'syslog.txt',
        'file_type': 'TXT',
        'analysis_result': {
            'error': '파일 형식을 인식할 수 없습니다.'
        }
    },
    {
        'filename': 'credit.csv',
        'file_type': 'CSV',
        'analysis_result': {
            'summary': '신용 데이터 분석',
            'total_records': 10000,
            'features': 15,
            'missing_values': 234,
            'anomaly_score': 0.05
        }
    },
    {
        'filename': 'systemlog.csv',
        'file_type': 'CSV',
        'analysis_result': {}
    },
    {
        'filename': 'customer.csv',
        'file_type': 'CSV',
        'analysis_result': {
            'summary': '고객 데이터 분석',
            'total_customers': 5000,
            'segments': 4,
            'churn_rate': 0.12,
            'avg_revenue': 1250.50
        }
    },
    {
        'filename': 'log_20250611.log',
        'file_type': 'LOG',
        'analysis_result': {
            'summary': '2025년 6월 11일 로그 분석',
            'total_events': 3421,
            'error_events': 45,
            'critical_events': 3
        }
    }
]

# 데이터 생성
created_sessions = []
base_time = timezone.now() - timedelta(days=10)

for i, data in enumerate(test_data):
    session = AnalysisSession.objects.create(
        session_id=str(uuid.uuid4()),
        original_filename=data['filename'],
        file_path=f'/tmp/{data["filename"]}',
        file_type=data['file_type'].lower(),
        analysis_result=data['analysis_result'],
        created_at=base_time + timedelta(days=i),
        updated_at=base_time + timedelta(days=i, hours=1),
    )
    created_sessions.append(session)
    print(f"Created: {session.original_filename}")

print(f"\n총 {len(created_sessions)}개의 테스트 세션이 생성되었습니다!")
print("이제 /dashboard/에서 확인해보세요.")