FROM python:3.10-slim-buster

# 사용자 및 그룹 ID 설정
ARG UID=1000
ARG GID=1000

# 비대화식 모드 설정
ENV DEBIAN_FRONTEND=noninteractive

# 사용자 및 그룹 생성
RUN groupadd -g "${GID}" appgroup && \
    useradd --create-home --no-log-init -u "${UID}" \
    -g "${GID}" appuser

WORKDIR /server

# tzdata 설치 및 pip 업그레이드
RUN apt-get update && \
    apt-get install -y --no-install-recommends tzdata && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --upgrade pip

# 시간대 환경 변수 설정
ENV TZ=Asia/Seoul

# 시간대 설정
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone

# 필요 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 사용자로 전환
USER appuser:appgroup

# Python 환경 변수 설정
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 소스 코드 복사
COPY . .

# 포트 노출
EXPOSE 8000

# 실행 스크립트 실행
CMD ["/start.sh"]
