#!/bin/bash

# Start cron in the background as root
cron -f &

# Start uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000
