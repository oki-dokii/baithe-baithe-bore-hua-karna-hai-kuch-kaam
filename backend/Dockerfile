FROM python:3.12.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY nwis ./nwis
COPY alembic.ini ./
COPY migrations ./migrations
RUN pip install --no-cache-dir uv==0.11.4 \
    && uv sync --frozen --no-dev --no-cache

ENV PATH="/app/.venv/bin:$PATH"

RUN useradd --create-home --uid 10001 nwis
USER nwis
