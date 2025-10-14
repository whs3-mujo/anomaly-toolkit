FROM python:3.11-slim
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 시스템 패키지 설치 (ML 라이브러리 컴파일에 필요) + 한글 폰트
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    libgomp1 \
    fontconfig \
    fonts-nanum \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -fv

WORKDIR /app

# requirements.txt 복사 및 의존성 설치 (캐시 최적화)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY . /app

# 미디어 디렉토리 생성 및 권한 설정
RUN mkdir -p /app/media/uploads && \
    mkdir -p /app/staticfiles && \
    chmod 755 /app/media /app/media/uploads

# 엔트리포인트 스크립트 권한 설정
RUN chmod +x /app/docker-entrypoint.sh && \
    sed -i 's/\r$//' /app/docker-entrypoint.sh

EXPOSE 8000

CMD ["/app/docker-entrypoint.sh"]