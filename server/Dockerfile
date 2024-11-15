# Python 이미지 사용
FROM python:3.10-slim-buster

# 빌드 인자로 UID와 GID 설정 (기본값: 1000)
ARG UID=1000
ARG GID=1000

# 비루트 사용자 생성 및 설정
RUN groupadd -g "${GID}" appgroup && \
    useradd -u "${UID}" -g "${GID}" -m appuser

# 작업 디렉토리 설정 및 소유권 변경
WORKDIR /app
COPY --chown=appuser:appgroup . /app

# 필요한 패키지 설치 (root 권한 필요)
RUN apt-get update && \
    apt-get install -y cron && \
    rm -rf /var/lib/apt/lists/*

# Python 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 환경 변수 설정
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# crontab 설정 파일 복사 및 적용
COPY mycron.txt /etc/cron.d/mycron
RUN chmod 0644 /etc/cron.d/mycron && crontab /etc/cron.d/mycron

# entrypoint.sh 스크립트 복사 및 실행 권한 부여
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# timezone 설정
ENV TZ=Asia/Seoul
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 애플리케이션 포트 설정
EXPOSE 8000

# 루트 권한으로 실행하여 cron이 정상 동작하도록 설정
USER root

# 엔트리포인트 스크립트를 실행
ENTRYPOINT ["/entrypoint.sh"]
