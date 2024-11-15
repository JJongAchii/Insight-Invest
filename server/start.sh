#!/bin/bash

# Celery 워커를 백그라운드로 실행
celery -A app.celery_app.celery_app worker --loglevel=info &

# Celery Beat를 백그라운드로 실행
celery -A app.celery_app.celery_app beat --loglevel=info &

# FastAPI 애플리케이션 실행
uvicorn app.main:app --host 0.0.0.0 --port 8000
