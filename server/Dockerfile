FROM python:3.10-slim-buster

# Install cron
RUN apt-get update && \
    apt-get install -y cron && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /server

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy application code
COPY . .

# Copy crontab file and apply cron job
COPY mycron.txt /etc/cron.d/mycron.txt
RUN chmod 0644 /etc/cron.d/mycron.txt

# Apply cron job
RUN crontab /etc/cron.d/mycron.txt

# Copy and set permissions for the entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set timezone
ENV TZ=Asia/Seoul
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Expose the application port
EXPOSE 8000

# Use the entrypoint script to start the container
ENTRYPOINT ["/entrypoint.sh"]
