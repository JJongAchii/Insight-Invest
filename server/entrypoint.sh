#!/bin/bash

# Start cron in the foreground to avoid PID file creation
cron -f &

# Start uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000
