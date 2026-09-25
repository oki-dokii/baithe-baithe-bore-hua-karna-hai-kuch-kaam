FROM postgres:17.6-bookworm

# Both extensions come from PostgreSQL's apt repository shipped in the base image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       postgresql-17-postgis-3 \
       postgresql-17-pgvector \
    && rm -rf /var/lib/apt/lists/*
