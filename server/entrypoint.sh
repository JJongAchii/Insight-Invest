#!/bin/bash

# Start cron in the background
cron &

# Start uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000
