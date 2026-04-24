FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY worker ./worker
COPY api ./api

RUN pip install --no-cache-dir ./api ./worker

CMD ["python", "-m", "worker.app.main"]
