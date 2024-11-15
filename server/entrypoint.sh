#!/bin/bash

# Start cron with custom PID file location
cron -f -L 15 &

# Start uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000
