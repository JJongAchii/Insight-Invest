FROM python:3.10-slim

ARG UID=1000
ARG GID=1000

RUN groupadd -g "${GID}" appgroup && \
    useradd --create-home --no-log-init -u "${UID}" -g "${GID}" appuser

WORKDIR /server

RUN apt-get update && \
    pip install --upgrade pip

COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

USER appuser:appgroup
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ENV TZ=Asia/Seoul

COPY server/ .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
