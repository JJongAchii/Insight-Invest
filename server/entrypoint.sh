#!/bin/bash

# cron을 루트 권한으로 실행
sudo cron -f &

# uvicorn을 비루트 사용자로 실행
sudo -u appuser uvicorn app.main:app --host 0.0.0.0 --port 8000
