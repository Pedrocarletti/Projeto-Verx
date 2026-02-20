FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install --no-install-recommends -y chromium chromium-driver \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --upgrade pip \
    && pip install .

RUN adduser --disabled-password --gecos "" appuser \
    && mkdir -p /app/output /app/.cache/yahoo_crawler \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

ENV YAHOO_CRAWLER_API_HOST=0.0.0.0 \
    YAHOO_CRAWLER_API_PORT=8000

CMD ["python", "-m", "uvicorn", "yahoo_crawler.api:app", "--host", "0.0.0.0", "--port", "8000"]
