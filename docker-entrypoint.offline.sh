#!/bin/bash

# 데이터베이스 마이그레이션
echo "데이터베이스 마이그레이션 실행 중..."
python manage.py makemigrations web
python manage.py migrate

# 정적 파일 수집
echo "정적 파일 수집 중..."
python manage.py collectstatic --noinput

# 로그 디렉토리 권한 확인
mkdir -p /app/logs
chmod -R 755 /app/logs
chmod -R 755 /app/media

echo "서버 시작 중..."
# Gunicorn으로 Django 앱 실행
gunicorn --timeout=300 --workers=4 config.wsgi -b 0.0.0.0:8000