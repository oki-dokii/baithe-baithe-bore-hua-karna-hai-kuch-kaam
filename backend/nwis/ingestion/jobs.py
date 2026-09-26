"""Durable, leased ingestion. Only the current lease holder may publish evidence."""

from uuid import uuid4

from psycopg.types.json import Jsonb

from nwis.config import get_settings
from nwis.db import connection
from nwis.ingestion.contracts import IngestionFailure
from nwis.ingestion.extract import (
    PROMPT_VERSION,
    RULES_VERSION,
    SCHEMA_VERSION,
    extract_candidates,
    quote_is_supported,
)
from nwis.ingestion.normalize import normalization_context, normalize
from nwis.ingestion.pages import read_pages
from nwis.ingestion.storage import path_for


def tick() -> bool:
    settings = get_settings()
    with connection() as conn:
        conn.execute("""INSERT INTO service_heartbeat(service) VALUES ('ingestion')
            ON CONFLICT(service) DO UPDATE SET last_seen_at=now()""")
        job = conn.execute("""SELECT * FROM ingestion_job WHERE
            (status IN ('pending','retrying') AND next_attempt_at<=now()) OR
            (status='processing' AND leased_until<now())
            ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1""").fetchone()
        if not job:
            return False
        if job["run_id"]:
            conn.execute(
                """UPDATE extraction_run SET status='failed', error_code='lease_expired',
                finished_at=now() WHERE id=%s AND status='processing'""",
                (job["run_id"],),
            )
        if job["attempts"] >= settings.job_max_attempts:
            conn.execute(
                """UPDATE ingestion_job SET status='failed', error_code='attempts_exhausted',
                error_message='Processing attempts exhausted', updated_at=now() WHERE id=%s""",
                (job["id"],),
            )
            conn.execute(
                "UPDATE source_document SET ingest_status='failed' WHERE id=%s",
                (job["document_id"],),
            )
            return True
        claim, run = uuid4(), uuid4()
        conn.execute(
            """UPDATE ingestion_job SET status='processing', attempts=attempts+1,
            claim_token=%s, run_id=%s, leased_until=now()+%s*interval '1 second',
            pages_done=0, updated_at=now() WHERE id=%s""",
            (claim, run, settings.job_lease_s, job["id"]),
        )
        conn.execute(
            "UPDATE source_document SET ingest_status='processing' WHERE id=%s",
            (job["document_id"],),
        )
        conn.execute(
            """INSERT INTO extraction_run(id,document_id,extractor_version,schema_version,status,
            provider,model_id,prompt_version) VALUES(%s,%s,%s,%s,'processing',%s,%s,%s)""",
            (
                run,
                job["document_id"],
                RULES_VERSION if settings.extraction_provider == "local_rules" else "structured-v1",
                SCHEMA_VERSION,
                settings.extraction_provider,
                settings.llm_model or None,
                PROMPT_VERSION,
            ),
        )
        document = conn.execute(
            """SELECT d.*, ds.kind, b.wellbore_id FROM source_document d
            JOIN dataset ds ON ds.id=d.dataset_id JOIN document_wellbore b ON b.document_id=d.id
            WHERE d.id=%s""",
            (job["document_id"],),
        ).fetchone()
        context = normalization_context(conn, document["wellbore_id"])

    def heartbeat(*_args):
        with connection() as conn:
            conn.execute(
                "UPDATE service_heartbeat SET last_seen_at=now() WHERE service='ingestion'"
            )
            updated = conn.execute(
                """UPDATE ingestion_job SET leased_until=now()+%s*interval '1 second',
                updated_at=now() WHERE id=%s AND claim_token=%s AND status='processing'
                RETURNING id""",
                (settings.job_lease_s, job["id"], claim),
            ).fetchone()
            if not updated:
                raise IngestionFailure("lease_lost", "Another worker owns this job")

    try:
        pages = read_pages(
            path_for(document["storage_key"]), document["mime_type"], str(run), heartbeat
        )
        extracted = []
        for page in pages:
            heartbeat()
            candidates = extract_candidates(page.text, document["kind"])
            if len(candidates) > 100:
                raise IngestionFailure(
                    "too_many_candidates", "Page exceeds the 100-candidate limit"
                )
            for candidate in candidates:
                if not quote_is_supported(candidate.quote, page.text):
                    raise IngestionFailure(
                        "unsupported_quote", "An extracted quote is not present on its source page"
                    )
            extracted.append((page, candidates))
            with connection() as conn:
                conn.execute(
                    "UPDATE ingestion_job SET pages_done=%s WHERE id=%s AND claim_token=%s",
                    (len(extracted), job["id"], claim),
                )
        heartbeat()
        with connection() as conn:
            current = conn.execute(
                "SELECT claim_token,status FROM ingestion_job WHERE id=%s FOR UPDATE", (job["id"],)
            ).fetchone()
            if current["claim_token"] != claim or current["status"] != "processing":
                return True
            for page, candidates in extracted:
                passage = uuid4()
                conn.execute(
                    """INSERT INTO extracted_passage(id,document_id,page_number,raw_text,ocr_applied,
                    ocr_confidence,text_version,preview_key,word_boxes,extraction_run_id)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        passage,
                        document["id"],
                        page.number,
                        page.text,
                        page.ocr_applied,
                        page.ocr_confidence,
                        job["generation"],
                        page.preview_key,
                        Jsonb(page.word_boxes or []),
                        run,
                    ),
                )
                for candidate in candidates:
                    normalized, issues = normalize(candidate, context)
                    if page.ocr_applied:
                        issues.append("ocr_source_verify")
                    fields = Jsonb(candidate.model_dump())
                    conn.execute(
                        """INSERT INTO document_event_draft(id,document_id,run_id,passage_id,
                        original_fields,current_fields,normalized_fields,issues) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (
                            uuid4(),
                            document["id"],
                            run,
                            passage,
                            fields,
                            fields,
                            Jsonb(normalized),
                            Jsonb(issues),
                        ),
                    )
            conn.execute(
                "UPDATE extraction_run SET status='completed',finished_at=now() WHERE id=%s", (run,)
            )
            conn.execute(
                "UPDATE ingestion_job SET status='completed',stage='review',leased_until=NULL,updated_at=now() WHERE id=%s",
                (job["id"],),
            )
            conn.execute(
                "UPDATE source_document SET ingest_status='needs_review',page_count=%s WHERE id=%s",
                (len(pages), document["id"]),
            )
    except Exception as exc:
        failure = (
            exc
            if isinstance(exc, IngestionFailure)
            else IngestionFailure(
                "processing_error", "Processing failed; inspect worker logs or retry"
            )
        )
        state = (
            "retrying"
            if failure.retryable and job["attempts"] + 1 < settings.job_max_attempts
            else "failed"
        )
        with connection() as conn:
            current = conn.execute(
                "SELECT claim_token FROM ingestion_job WHERE id=%s FOR UPDATE", (job["id"],)
            ).fetchone()
            if current["claim_token"] != claim:
                return True
            conn.execute(
                """UPDATE ingestion_job SET status=%s,error_code=%s,error_message=%s,
                next_attempt_at=now()+interval '30 seconds',leased_until=NULL,updated_at=now() WHERE id=%s""",
                (state, failure.code, failure.message, job["id"]),
            )
            conn.execute(
                "UPDATE extraction_run SET status='failed',error_code=%s,finished_at=now() WHERE id=%s",
                (failure.code, run),
            )
            conn.execute(
                "UPDATE source_document SET ingest_status=%s WHERE id=%s", (state, document["id"])
            )
    return True
