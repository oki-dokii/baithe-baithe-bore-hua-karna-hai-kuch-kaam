# Optional local semantic search

This implementation adds **local vector retrieval over approved, cited event claims**. It does not embed raw report pages, unreviewed drafts or entire OCR output; it does not send document text to an external model. The UI always states whether exact-term or related-meaning retrieval ran. Results are historical evidence candidates with original citations, never generated answers or drilling recommendations.

## Setup

The Compose backend includes the optional FastEmbed runtime but starts with `NWIS_SEMANTIC_ENABLED=false`. For a host installation, run `uv sync --frozen --extra dev --extra semantic` in `backend/`. To prepare model weights explicitly (public download, no report upload), run from `backend/`:

```sh
.venv/bin/python -m nwis.semantic prepare
```

The pinned `BAAI/bge-small-en-v1.5` model produces 384-dimensional embeddings. The default ignored cache is `backend/storage/models`; Compose uses the shared `/app/storage/models` volume. API and worker inference use `local_files_only=True`, so a missing model fails closed without starting a download. To prepare Compose, use `docker compose exec api python -m nwis.semantic prepare` after the stack starts.

Run the additive migration with `python -m nwis.initialize` or the Compose `migrate` service. Backfill only approved, cited claims, optionally limited to one dataset:

```sh
.venv/bin/python -m nwis.semantic index --dataset-id YOUR_DATASET_UUID
```

Then set `NWIS_SEMANTIC_ENABLED=true` for both API and ingestion worker and restart them. The worker scans for newly approved or corrected claims every 30 seconds; `index` is idempotent. The browser obtains capability state from `GET /api/v1/search-capabilities`; `POST /api/v1/query` accepts `mode: "semantic"` or the unchanged default `"full_text"`. A semantic request returns 503 when disabled or unprepared rather than silently changing modes. Full-text remains available.

## Safety and evaluation limits

- The index stores only event type, approved description and approved source quote. Search rechecks `review_state='approved'`, citation existence, dataset and filters. A content hash excludes embeddings stale after a claim correction until reindexed.
- Vector cosine ranking uses a **provisional 0.62 candidate cutoff**. This was tightened after a one-source synthetic probe found unrelated drilling questions at 0.58–0.60, while a supported paraphrase scored 0.64. It is not calibrated for drilling language, false matches or no-support questions. Never interpret similarity as event risk, answer confidence or model accuracy. The existing fixed-question evaluator now accepts an explicit semantic mode, but no real-report semantic score is claimed.
- A report can contain several events; the index is event-level, not a whole-page vector. The UI offers no generated advice. The NOD-511 disputed event remains unapproved and unindexed.
- Model weights are downloaded only during explicit preparation; check deployment licensing, network and private-data policy before enabling this on OIL material.

The fresh local preview rehearsal is in [Phase 6](../phase-6/semantic-preview-rehearsal-2026-09-27.md). The public-report benchmark still needs independent review and approved passage IDs before real-source retrieval evaluation.
