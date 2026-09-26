# Phase 2 — Evidence ingestion and review

Implemented on 2026-09-25. This is a prototype implementation, not a qualified drilling system. The real-source gate remains open. A [Norwegian Offshore Directorate scanned-report trial](real-source-qualification.md) now exercises all 58 pages and stages two cited incidents, but neither is approved for operational use.

## What works

- Reviewer/engineer report upload with dataset/wellbore identity, SHA-256 deduplication and transactional idempotency receipts. PDF signature or UTF-8 `.txt` validation; default 25 MiB, 50-page and 30,000-character/page limits.
- PostgreSQL job claiming with `FOR UPDATE SKIP LOCKED`, leased ownership tokens, bounded transient retries, visible terminal errors and explicit failed-job retry. Extraction runs retain version/provider metadata. A lost lease cannot publish pages or events.
- Poppler text extraction and original-page PNGs. Low-text pages use English Tesseract OCR; word boxes and mean word confidence are retained. OCR confidence is not event confidence. Mixed scanned/text regions on an otherwise text-rich page are not comprehensively detected yet.
- Conservative local incident matching, plus an optional schema-validated OpenAI-compatible Chat Completions adapter. Quotes are checked against source text; report instructions are treated as untrusted data. Private datasets cannot use the remote adapter.
- Source units/axis/datum retained. Feet convert to metres, but TVD is never silently treated as MD. Missing or conflicting datum, unknown units, unresolved formation and OCR sources produce review flags. Approved aliases are scoped to the dataset. No automatic trajectory mapping occurs here.
- Candidate staging separate from canonical events. Reviewer corrections, approval/rejection and manually added source-backed candidates use optimistic versions and record actor, time, rationale, and before/after fields. Approval creates event/passage, mitigation, outcome and NPT relationships atomically.
- Finalized candidates cannot be edited in this phase. A future supersession workflow is needed for revocation. Approved records with quality flags remain unsuitable for automatic correlation/alerts until those flags are handled in later phases.
- Editorial evidence room: light paper palette, system serif headlines, restrained green, report index/source/evidence columns, original-page/text toggle, retry states, manual additions, history and responsive layout. No external fonts or image assets are required. The Phase 1 well directory remains available.

## Run

Use the Phase 1 `.env` instructions, then:

```sh
docker compose up --build -d --wait
docker compose exec api python -m nwis.smoke
```

The additive migration is `0003_document_ingestion`. `document_storage` is shared by API and worker and must be backed up with PostgreSQL. Do not delete volumes when updating. The default provider is `local_rules`; no model key is required.

For a remote provider, configure `NWIS_EXTRACTION_PROVIDER=openai_compatible`, `NWIS_LLM_BASE_URL`, `NWIS_LLM_MODEL`, and `NWIS_LLM_API_KEY`. A selected endpoint must support strict JSON-schema output. No live provider has been validated in this phase; mock tests validate the request/output contract. Consult the [official structured-output guide](https://developers.openai.com/api/docs/guides/structured-outputs). Never commit credentials, and do not upload confidential material for remote processing. The adapter blocks datasets labeled private, but classification still depends on correct ingestion metadata.

Sign in using the reviewer token from your local environment, choose **Add a report**, select the correct wellbore, and upload a PDF/text report. Check the original source and quality issues before approving. A viewer sees approved claims only; original pages and draft fields are reviewer/admin-only. An engineer can submit reports and see their processing state, but cannot review them.

For host development, set `NWIS_DATABASE_URL` to the correct development port, run `python -m nwis.initialize`, `uvicorn nwis.main:app`, and `python -m nwis.worker` from `backend` with the environment loaded. Set `NWIS_DEV_API_URL` when starting Vite if the API is not on port 8000.

Current local verification uses database port **15432**, API **18081**, frontend **13001**. The existing Phase 1 containers remain separate; their old API/frontend images do not contain Phase 2 code. Set `NWIS_DB_PORT=15432` in local configuration to preserve the database port on later Compose runs. Container disk space was too low for another full local image build, so CI is configured to verify a fresh container build.

## Verification

From `backend`:

```sh
uv sync --frozen --extra dev
uv run --frozen --extra dev ruff check nwis migrations tests
uv run --frozen --extra dev pytest -q
# Against an initialized development/test DB with role tokens and NWIS_DATABASE_URL set:
NWIS_INTEGRATION=1 uv run --frozen --extra dev pytest -q tests/test_ingestion_integration.py
```

PDF tests require `pdfinfo`, `pdftotext`, `pdftoppm`, and `tesseract` on PATH. Tests generate owned synthetic PDFs, including a raster-only scan; they are not real well records. Integration tests retain their synthetic documents and audit history in the selected database; use a development/test database only.

`frontend/ui-smoke.mjs` uses Playwright, a running API/worker/frontend and `NWIS_REVIEWER_TOKEN`. Set `NWIS_UI_URL` for another URL; optionally `NWIS_PLAYWRIGHT_MODULE` to an installed module and `NWIS_CHROME_PATH` to Chrome. It uploads and approves a fictional report, checks final-record locking, mobile overflow, well-directory navigation and browser errors. Screenshots are ignored under `frontend/artifacts/`.

Acceptance coverage: ING-01 exercises text and scanned reports through upload/extract/review; ING-02 tests nulls, unit conversion, axis separation and invalid intervals; ING-03 covers duplicate uploads/approvals, corrections and provenance. Role denials are enforced but denial-audit coverage, dataset-specific authorization, production identity and malware scanning remain hardening work (OPS-02 is not fully complete).

## Open gates and limits

1. **Real public report qualification:** the [NOD 25/10-2 R trial](real-source-qualification.md) processed a 58-page scanned report and produced two page-cited drafts, but neither was approved. Source depth and the NOD summary disagree, and the report's MD/datum/formation and redistribution rights need review. Volve remains a separate candidate. An earlier, approximately 101 MiB Sodir report download timed out and was not used. Never relabel foreign wells as OIL/Assam observations.
2. **Live model extraction:** provider/model/budget remain unselected. The local regex baseline misses complex prose, tables, cross-page context and many mitigation links. Reviewers must inspect sources and add missed evidence. Empty extraction does not mean no incidents.
3. **Structured programs:** automated casing/cement/mud-program extraction is not implemented; the foundation tables remain. This phase structures incident evidence and associated mitigation/outcome/NPT, not every report field named in the problem statement.
4. **Safety/scale:** no live eRTMAC, predictions, operational recommendations, formation correlation or alerts yet. Reports are limited to a single selected wellbore. The index currently shows the latest 100 visible uploaded documents. Storage is local filesystem, not object storage. Retention/orphan cleanup, large-document streaming, comprehensive audit denials and adversarial parser hardening need follow-up.
5. **Performance:** small owned test fixtures pass quickly; no real-report latency benchmark or extraction-accuracy claim is established.

The selected editorial direction follows the user's preference: a restrained working archive rather than a generic analytics dashboard. No external design-generation service was used.
