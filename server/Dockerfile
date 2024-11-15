FROM python:3.10-slim-buster

ARG UID=1000
ARG GID=1000

RUN groupadd -g "${GID}" appgroup && \
    useradd --create-home --no-log-init -u "${UID}" -g "${GID}" appuser

WORKDIR /server

RUN apt-get update && \
    pip install --upgrade pip && \
    apt-get install -y cron

COPY crontab /etc/cron.d/update_price_cron
RUN chmod 0644 /etc/cron.d/update_price_cron
RUN crontab /etc/cron.d/update_price_cron

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

USER appuser:appgroup
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ENV TZ=Asia/Seoul  

COPY . .

EXPOSE 8000

CMD cron && uvicorn main:app --host 0.0.0.0 --port 8000