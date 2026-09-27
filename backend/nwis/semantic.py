"""Opt-in, local-only semantic index over approved and cited event claims."""

import argparse
import hashlib
import json
import math
import os
from functools import lru_cache
from pathlib import Path
from uuid import UUID

from nwis.db import connection

MODEL_ID = "BAAI/bge-small-en-v1.5"
DIMENSION = 384
MIN_COSINE = 0.62  # Conservative synthetic-demo cutoff, not a calibrated relevance threshold.


class SemanticUnavailable(RuntimeError):
    pass


def claim_text(event: dict) -> str:
    """Never include whole source pages or unapproved draft text in embeddings."""
    return "\n".join(
        (event["event_type"], event.get("description") or "", event.get("quote") or "")
    )


def claim_hash(event: dict) -> str:
    return hashlib.sha256(claim_text(event).encode()).hexdigest()


def vector_literal(values) -> str:
    numbers = list(values)
    if len(numbers) != DIMENSION or not all(math.isfinite(float(v)) for v in numbers):
        raise ValueError("Embedding dimension or numeric values are invalid")
    return "[" + ",".join(format(float(value), ".9g") for value in numbers) + "]"


@lru_cache(maxsize=2)
def model(allow_download: bool = False):
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:
        raise SemanticUnavailable("Optional local embedding runtime is not installed") from exc
    cache = Path(os.getenv("NWIS_SEMANTIC_CACHE_DIR", "storage/models"))
    cache.mkdir(parents=True, exist_ok=True)
    try:
        return TextEmbedding(
            model_name=MODEL_ID,
            cache_dir=str(cache),
            local_files_only=not allow_download,
            threads=2,
        )
    except Exception as exc:
        raise SemanticUnavailable("Local semantic model is not prepared") from exc


def query_vector(question: str) -> str:
    try:
        return vector_literal(next(iter(model().query_embed(question))))
    except Exception as exc:
        raise SemanticUnavailable("Local semantic model could not embed the query") from exc


def prepare_model() -> dict:
    vector_literal(next(iter(model(True).query_embed("drilling mud loss"))))
    return {"model_id": MODEL_ID, "dimension": DIMENSION, "ready": True}


def index_approved(dataset_id: UUID | None = None) -> dict:
    """Idempotent explicit backfill; no background inference or external report transfer."""
    embedder = model()
    indexed = 0
    unchanged = 0
    with connection() as conn:
        rows = conn.execute(
            """SELECT e.id,e.event_type,e.description,e.source_fields->>'quote' AS quote,
                      s.model_id,s.content_sha256
               FROM drilling_event e JOIN wellbore b ON b.id=e.wellbore_id
               JOIN well w ON w.id=b.well_id
               LEFT JOIN event_embedding s ON s.event_id=e.id
               WHERE e.review_state='approved'
                 AND EXISTS (SELECT 1 FROM event_passage ep WHERE ep.event_id=e.id)
                 AND coalesce(e.source_fields->>'quote','') <> ''
                 AND (%s::uuid IS NULL OR w.dataset_id=%s)
               ORDER BY e.id""",
            (dataset_id, dataset_id),
        ).fetchall()
        for row in rows:
            digest = claim_hash(row)
            if row["model_id"] == MODEL_ID and row["content_sha256"] == digest:
                unchanged += 1
                continue
            vector = vector_literal(next(iter(embedder.passage_embed([claim_text(row)]))))
            conn.execute(
                """INSERT INTO event_embedding(event_id,model_id,content_sha256,embedding)
                   VALUES (%s,%s,%s,%s::vector)
                   ON CONFLICT (event_id) DO UPDATE SET model_id=EXCLUDED.model_id,
                   content_sha256=EXCLUDED.content_sha256,embedding=EXCLUDED.embedding,
                   indexed_at=now()""",
                (row["id"], MODEL_ID, digest, vector),
            )
            indexed += 1
    return {"model_id": MODEL_ID, "indexed": indexed, "unchanged": unchanged}


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare or backfill local semantic search")
    parser.add_argument("command", choices=("prepare", "index"))
    parser.add_argument("--dataset-id", type=UUID)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare_model()
    else:
        result = index_approved(args.dataset_id)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
