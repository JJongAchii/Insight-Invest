#!/bin/bash

# cron을 백그라운드에서 루트로 실행
cron &

# uvicorn을 비루트 사용자로 실행
su - appuser -c "uvicorn app.main:app --host 0.0.0.0 --port 8000"
