#!/bin/bash

# Start supercronic with your crontab
/usr/local/bin/supercronic /server/mycron.txt &

# Start uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000
