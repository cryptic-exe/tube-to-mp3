FROM python:3.12-slim

RUN apt-get update \
  && apt-get install -y --no-install-recommends ffmpeg \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Shared package + API requirements
COPY packages/shared /app/packages/shared
COPY services/api/requirements.txt /app/services/api/requirements.txt

RUN pip install --no-cache-dir -r /app/services/api/requirements.txt \
  && pip install --no-cache-dir /app/packages/shared

COPY services/api/app /app/services/api/app

ENV PYTHONUNBUFFERED=1 \
    JOBS_DIR=/tmp/yt-mp3-jobs \
    PYTHONPATH=/app/packages/shared:/app/services/api

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "/app/services/api"]