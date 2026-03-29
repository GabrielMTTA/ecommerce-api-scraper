FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1001 scraper && \
    mkdir -p /app && \
    chown -R scraper:scraper /app

COPY requirements.txt ./

RUN pip install --no-cache-dir --disable-pip-version-check -r requirements.txt

COPY base_scraper.py ./
COPY scrapers ./scrapers

USER scraper

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD python -c "import redis; redis.Redis().ping()" || exit 1

CMD ["python", "-m", "rq", "worker", "default"]
