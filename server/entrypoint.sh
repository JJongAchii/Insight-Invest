#!/bin/bash

# cron을 백그라운드에서 실행하며, PID 파일을 /tmp에 생성하도록 설정
cron -L 15 -f /tmp/crond.pid &

# uvicorn 서버 실행
uvicorn app.main:app --host 0.0.0.0 --port 8000
