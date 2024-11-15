#!/bin/bash

# cron을 백그라운드에서 실행
cron &

# uvicorn 서버를 비루트 사용자로 실행
runuser -u appuser -- uvicorn app.main:app --host 0.0.0.0 --port 8000
