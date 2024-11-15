#!/bin/bash

# Start cron with custom PID file location
cron -f -L 15 -p /tmp/cron.pid &
