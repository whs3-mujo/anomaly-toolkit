#!/bin/bash

# 데이터베이스 마이그레이션
echo "Running database migrations..."
python manage.py makemigrations web
python manage.py migrate

# 정적 파일 수집
echo "Collecting static files..."
echo yes | python manage.py collectstatic --clear

# 서버 시작
echo "Starting server..."
exec gunicorn --timeout=600 --workers=2 --threads=4 --bind 0.0.0.0:8000 config.wsgi:application