FROM python:3.12.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md ./
COPY nwis ./nwis
COPY alembic.ini ./
COPY migrations ./migrations
RUN pip install --no-cache-dir uv==0.11.4 \
    && uv sync --frozen --no-dev --no-cache

ENV PATH="/app/.venv/bin:$PATH"

RUN useradd --create-home --uid 10001 nwis && mkdir /app/storage && chown nwis:nwis /app/storage
USER nwis
