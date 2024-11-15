FROM python:3.10-slim-buster

# Install cron
RUN apt-get update && \
    apt-get install -y cron && \
    rm -rf /var/lib/apt/lists/*

# Create a non-root user and group with UID and GID 1000
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -s /bin/bash -m appuser

# Set working directory and change ownership
WORKDIR /server
COPY . /server
RUN chown -R appuser:appuser /server

# Install Python dependencies
USER appuser
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy crontab file and apply cron job
USER root
COPY mycron.txt /etc/cron.d/mycron
RUN chmod 0644 /etc/cron.d/mycron && \
    chown root:root /etc/cron.d/mycron

# Change the cron PID file location to a writable directory
RUN sed -i 's|/var/run/cron.pid|/tmp/cron.pid|g' /etc/crontab /etc/init.d/cron

# Set timezone
ENV TZ=Asia/Seoul
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Expose the application port
EXPOSE 8000

# Copy and set permissions for the entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && chown appuser:appuser /entrypoint.sh

# Switch back to non-root user
USER appuser

# Use the entrypoint script to start the container
ENTRYPOINT ["/entrypoint.sh"]

# Set the default command to run uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
