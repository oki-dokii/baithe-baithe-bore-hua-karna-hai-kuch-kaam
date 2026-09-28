import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from nwis.config import get_settings
from nwis.db import connection
from nwis.decision_ledger import append_decision, text_digest
from nwis.ingestion.contracts import Candidate, ManualCandidateRequest, ReviewRequest
from nwis.ingestion.extract import local_candidates, quote_is_supported
from nwis.ingestion.normalize import normalization_context, normalize
from nwis.ingestion.storage import path_for, store_blob
from nwis.provenance import may_approve_event
from nwis.security import Principal, current_principal, require_role
from nwis.voice import local_asr_available

router = APIRouter(prefix="/api/v1")


class TranscriptCorrection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_review_version: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=30000)
    rationale: str = Field(min_length=3, max_length=2000)


def receipt(conn, actor, key, payload):
    if not 8 <= len(key) <= 128:
        raise HTTPException(422, "Idempotency-Key must contain 8–128 characters")
    digest = hashlib.sha256(
        json.dumps(jsonable_encoder(payload), sort_keys=True).encode()
    ).hexdigest()
    conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (actor + ":" + key,))
    old = conn.execute(
        "SELECT * FROM request_receipt WHERE actor_name=%s AND idempotency_key=%s", (actor, key)
    ).fetchone()
    if old and old["request_hash"] != digest:
        raise HTTPException(409, "Idempotency key was already used for a different request")
    return digest, old["response"] if old else None


def save_receipt(conn, actor, key, digest, response):
    conn.execute(
        "INSERT INTO request_receipt(actor_name,idempotency_key,request_hash,response) VALUES(%s,%s,%s,%s)",
        (actor, key, digest, Jsonb(jsonable_encoder(response))),
    )
    return response


@router.get("/me")
def me(principal: Principal = Depends(current_principal)):
    return {
        "name": principal.name,
        "role": principal.role,
        "extraction_provider": get_settings().extraction_provider,
        "document_max_pages": get_settings().document_max_pages,
        "voice_local_asr_available": local_asr_available(),
    }


@router.get("/document-options")
def options(_principal=Depends(require_role("reviewer", "engineer"))):
    with connection() as conn:
        return conn.execute("""SELECT b.id AS wellbore_id,w.name,b.external_id,d.id AS dataset_id,d.kind
            FROM wellbore b JOIN well w ON w.id=b.well_id JOIN dataset d ON d.id=w.dataset_id
            ORDER BY w.name""").fetchall()


@router.post("/documents", status_code=202)
async def upload(
    dataset_id: UUID = Form(...),
    wellbore_id: UUID = Form(...),
    file: UploadFile = File(...),
    idempotency_key: str = Header(...),
    principal=Depends(require_role("engineer", "reviewer")),
):
    limit = get_settings().upload_max_bytes
    content = bytearray()
    while chunk := await file.read(65536):
        content.extend(chunk)
        if len(content) > limit:
            raise HTTPException(413, "Document exceeds the configured upload limit")
    if not content:
        raise HTTPException(422, "Document is empty")
    if content.startswith(b"%PDF-"):
        mime = "application/pdf"
    else:
        try:
            text = content.decode("utf-8")
            if "\x00" in text or Path(file.filename or "").suffix.lower() != ".txt":
                raise ValueError
        except (ValueError, UnicodeDecodeError):
            raise HTTPException(415, "Upload a PDF or UTF-8 .txt report") from None
        mime = "text/plain"
    checksum = hashlib.sha256(content).hexdigest()
    with connection() as conn:
        digest, old = receipt(
            conn, principal.name, idempotency_key, ["upload", dataset_id, wellbore_id, checksum]
        )
        if old:
            return old
        valid = conn.execute(
            """SELECT d.kind FROM wellbore b JOIN well w ON w.id=b.well_id
            JOIN dataset d ON d.id=w.dataset_id WHERE b.id=%s AND d.id=%s""",
            (wellbore_id, dataset_id),
        ).fetchone()
        if not valid:
            raise HTTPException(422, "Wellbore does not belong to this dataset")
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (str(dataset_id) + checksum,)
        )
        existing = conn.execute(
            "SELECT id FROM source_document WHERE dataset_id=%s AND sha256=%s",
            (dataset_id, checksum),
        ).fetchone()
        if existing:
            link = conn.execute(
                "SELECT 1 FROM document_wellbore WHERE document_id=%s AND wellbore_id=%s",
                (existing["id"], wellbore_id),
            ).fetchone()
            if not link:
                raise HTTPException(
                    409, "This document is already linked to another wellbore; verify its identity"
                )
            return save_receipt(
                conn,
                principal.name,
                idempotency_key,
                digest,
                {"id": str(existing["id"]), "duplicate": True},
            )
        document_id, job_id = uuid4(), uuid4()
        key = f"documents/{dataset_id}/{checksum}"
        store_blob(key, bytes(content))
        conn.execute(
            """INSERT INTO source_document(id,dataset_id,external_id,storage_key,sha256,filename,
            mime_type,byte_size,access_class,uploaded_by) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                document_id,
                dataset_id,
                str(document_id),
                key,
                checksum,
                Path(file.filename or "report").name[:240],
                mime,
                len(content),
                valid["kind"],
                principal.name,
            ),
        )
        conn.execute(
            "INSERT INTO document_wellbore(document_id,wellbore_id) VALUES(%s,%s)",
            (document_id, wellbore_id),
        )
        conn.execute(
            "INSERT INTO ingestion_job(id,document_id,stage) VALUES(%s,%s,'extract')",
            (job_id, document_id),
        )
        conn.execute(
            "INSERT INTO audit_log(actor_name,action,entity_type,entity_id) VALUES(%s,'upload','document',%s)",
            (principal.name, document_id),
        )
        return save_receipt(
            conn,
            principal.name,
            idempotency_key,
            digest,
            {"id": str(document_id), "duplicate": False},
        )


@router.post("/voice-memos", status_code=202)
async def upload_voice_memo(
    dataset_id: UUID = Form(...), wellbore_id: UUID = Form(...),
    language: str = Form(...), consent: bool = Form(...),
    transcript: str = Form(""), audio: UploadFile = File(...),
    idempotency_key: str = Header(...),
    principal=Depends(require_role("engineer", "reviewer")),
):
    if not consent:
        raise HTTPException(422, "Explicit recording and retention consent is required")
    if language not in ("as", "hi", "en"):
        raise HTTPException(422, "Choose Assamese, Hindi or English")
    transcript = transcript.strip()
    if len(transcript) > get_settings().page_max_characters:
        raise HTTPException(422, "Transcript exceeds the page text limit")
    if not transcript and not local_asr_available():
        raise HTTPException(422, "Provide a typed transcript or configure local ASR")
    content = bytearray()
    while chunk := await audio.read(65536):
        content.extend(chunk)
        if len(content) > min(get_settings().upload_max_bytes, 8 * 1024 * 1024):
            raise HTTPException(413, "Voice memo exceeds the 8 MB limit")
    if len(content) < 44:
        raise HTTPException(415, "Voice memo audio is empty or invalid")
    if content[:4] == b"RIFF" and content[8:12] == b"WAVE":
        mime, extension = "audio/wav", "wav"
    elif content[:4] == b"\x1aE\xdf\xa3":
        mime, extension = "audio/webm", "webm"
    elif content[4:8] == b"ftyp":
        mime, extension = "audio/mp4", "m4a"
    else:
        raise HTTPException(415, "Upload WAV, WebM or M4A audio")
    checksum = hashlib.sha256(content).hexdigest()
    with connection() as conn:
        digest, old = receipt(conn, principal.name, idempotency_key,
                              ["voice_memo", dataset_id, wellbore_id, checksum,
                               language, hashlib.sha256(transcript.encode()).hexdigest()])
        if old:
            return old
        valid = conn.execute(
            """SELECT d.kind FROM wellbore b JOIN well w ON w.id=b.well_id
               JOIN dataset d ON d.id=w.dataset_id WHERE b.id=%s AND d.id=%s""",
            (wellbore_id, dataset_id),
        ).fetchone()
        if not valid:
            raise HTTPException(422, "Wellbore does not belong to this dataset")
        if conn.execute("SELECT 1 FROM source_document WHERE dataset_id=%s AND sha256=%s",
                        (dataset_id, checksum)).fetchone():
            raise HTTPException(409, "This audio is already archived")
        document_id, job_id = uuid4(), uuid4()
        key = f"voice/{dataset_id}/{checksum}.{extension}"
        store_blob(key, bytes(content))
        conn.execute(
            """INSERT INTO source_document
               (id,dataset_id,external_id,storage_key,sha256,filename,mime_type,
                byte_size,access_class,uploaded_by,doc_type)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'voice_memo')""",
            (document_id, dataset_id, str(document_id), key, checksum,
             f"voice-memo-{document_id}.{extension}", mime, len(content),
             valid["kind"], principal.name),
        )
        conn.execute("INSERT INTO document_wellbore(document_id,wellbore_id) VALUES(%s,%s)",
                     (document_id, wellbore_id))
        conn.execute(
            """INSERT INTO voice_memo(document_id,language,transcription_mode,
               typed_transcript,consent_at,audio_retention_until)
               VALUES (%s,%s,%s,%s,now(),now()+interval '30 days')""",
            (document_id, language, "typed" if transcript else "local_asr",
             transcript or None),
        )
        conn.execute("INSERT INTO ingestion_job(id,document_id,stage) VALUES(%s,%s,'extract')",
                     (job_id, document_id))
        conn.execute(
            "INSERT INTO audit_log(actor_name,action,entity_type,entity_id) VALUES(%s,'upload_voice_memo','document',%s)",
            (principal.name, document_id),
        )
        return save_receipt(conn, principal.name, idempotency_key, digest,
                            {"id": str(document_id), "doc_type": "voice_memo",
                             "transcription_mode": "typed" if transcript else "local_asr",
                             "audio_retention_days": 30})


@router.get("/documents")
def documents(principal=Depends(current_principal)):
    reviewer = principal.role in ("reviewer", "admin")
    with connection() as conn:
        return conn.execute(
            """SELECT d.id,d.filename,d.doc_type,d.ingest_status,d.page_count,d.created_at,ds.kind,
            ds.qualification_status,ds.origin_kind,ds.authorization_state,ds.applicability,
            (SELECT count(*) FROM document_event_draft c WHERE c.document_id=d.id AND c.state='needs_review') AS pending_count
            FROM source_document d JOIN dataset ds ON ds.id=d.dataset_id WHERE d.uploaded_by IS NOT NULL
            AND (%s OR d.uploaded_by=%s OR EXISTS(SELECT 1 FROM document_event_draft c WHERE c.document_id=d.id AND c.state='approved')
                OR EXISTS(SELECT 1 FROM reviewed_report_fact f JOIN extracted_passage p ON p.id=f.passage_id
                    WHERE p.document_id=d.id AND f.state='approved'))
            ORDER BY d.created_at DESC LIMIT 100""",
            (reviewer, principal.name),
        ).fetchall()


def get_document(conn, document_id, principal):
    document = conn.execute("SELECT * FROM source_document WHERE id=%s", (document_id,)).fetchone()
    if not document:
        raise HTTPException(404, "Document not found")
    reviewer = principal.role in ("reviewer", "admin")
    approved = conn.execute(
        """SELECT 1 WHERE EXISTS(SELECT 1 FROM document_event_draft
            WHERE document_id=%s AND state='approved')
            OR EXISTS(SELECT 1 FROM reviewed_report_fact f JOIN extracted_passage p ON p.id=f.passage_id
                WHERE p.document_id=%s AND f.state='approved')""",
        (document_id, document_id),
    ).fetchone()
    if not reviewer and document["uploaded_by"] != principal.name and not approved:
        raise HTTPException(404, "Document not found")
    return document, reviewer


@router.get("/documents/{document_id}")
def detail(document_id: UUID, principal=Depends(current_principal)):
    with connection() as conn:
        document, reviewer = get_document(conn, document_id, principal)
        provenance = conn.execute(
            """SELECT kind,qualification_status,origin_kind,authorization_state,applicability
            FROM dataset WHERE id=%s""",
            (document["dataset_id"],),
        ).fetchone()
        candidates = conn.execute(
            """SELECT c.*,p.page_number FROM document_event_draft c
            JOIN extracted_passage p ON p.id=c.passage_id WHERE c.document_id=%s AND (%s OR c.state='approved')
            ORDER BY p.page_number,c.created_at,c.id""",
            (document_id, reviewer),
        ).fetchall()
        # Draft pages may contain unrelated unreviewed claims. Non-reviewers only see approved quotes.
        if not reviewer:
            for candidate in candidates:
                candidate.pop("original_fields", None)
        pages = (
            conn.execute(
            """SELECT DISTINCT ON (page_number) id,page_number,raw_text,ocr_applied,ocr_confidence,
               transcription_confidence,transcription_confidence_kind,transcription_language,
               preview_key IS NOT NULL AS has_preview
            FROM extracted_passage WHERE document_id=%s ORDER BY page_number,text_version DESC""",
                (document_id,),
            ).fetchall()
            if reviewer
            else []
        )
        jobs = conn.execute(
            """SELECT id,status,attempts,pages_done,error_code,error_message FROM ingestion_job
            WHERE document_id=%s ORDER BY created_at DESC""",
            (document_id,),
        ).fetchall()
        audit = (
            conn.execute(
                """SELECT actor_name,action,rationale,recorded_at,entity_id,entity_version
            FROM review_decision WHERE document_id=%s ORDER BY recorded_at DESC LIMIT 100""",
                (document_id,),
            ).fetchall()
            if reviewer
            else []
        )
        return {
            "id": document_id,
            "dataset_id": document["dataset_id"],
            "filename": document["filename"],
            "doc_type": document["doc_type"],
            **provenance,
            "approval_allowed": may_approve_event(provenance),
            "ingest_status": document["ingest_status"],
            "review_version": document["review_version"],
            "pages": pages,
            "candidates": candidates,
            "jobs": jobs,
            "audit": audit,
        }


@router.get("/documents/{document_id}/audio")
def voice_audio(document_id: UUID, principal=Depends(current_principal)):
    with connection() as conn:
        document, reviewer = get_document(conn, document_id, principal)
        if document["doc_type"] != "voice_memo" or not (
            reviewer or document["uploaded_by"] == principal.name
        ):
            raise HTTPException(404, "Voice memo unavailable")
        memo = conn.execute(
            """SELECT audio_retention_until,audio_purged_at FROM voice_memo
               WHERE document_id=%s""", (document_id,)
        ).fetchone()
    if not memo or memo["audio_purged_at"] or memo["audio_retention_until"] <= datetime.now(timezone.utc):
        raise HTTPException(404, "Voice audio expired")
    audio_path = path_for(document["storage_key"])
    if not audio_path.is_file():
        raise HTTPException(404, "Voice audio unavailable")
    return FileResponse(audio_path, media_type=document["mime_type"],
                        headers={"Cache-Control": "no-store"})


@router.post("/voice-memos/{document_id}/transcript")
def correct_voice_transcript(
    document_id: UUID, body: TranscriptCorrection,
    idempotency_key: str = Header(...),
    principal=Depends(require_role("engineer", "reviewer")),
):
    corrected = body.text.strip()
    if not corrected or len(corrected) > get_settings().page_max_characters:
        raise HTTPException(422, "Corrected transcript is empty or too long")
    with connection() as conn:
        digest, old = receipt(conn, principal.name, idempotency_key,
                              ["correct_voice_transcript", document_id, body.model_dump()])
        if old:
            return old
        document = conn.execute("SELECT * FROM source_document WHERE id=%s FOR UPDATE",
                                (document_id,)).fetchone()
        if not document or document["doc_type"] != "voice_memo":
            raise HTTPException(404, "Voice memo not found")
        if principal.role not in ("reviewer", "admin") and document["uploaded_by"] != principal.name:
            raise HTTPException(403, "Only the uploader or a reviewer may correct this transcript")
        if document["review_version"] != body.expected_review_version:
            raise HTTPException(409, "Transcript changed; refresh before correcting")
        if conn.execute(
            "SELECT 1 FROM document_event_draft WHERE document_id=%s AND state='approved'",
            (document_id,),
        ).fetchone():
            raise HTTPException(409, "Approved claims require a new source version")
        memo = conn.execute(
            "SELECT language,audio_retention_until,audio_purged_at FROM voice_memo WHERE document_id=%s",
            (document_id,),
        ).fetchone()
        if not memo or memo["audio_purged_at"] or memo["audio_retention_until"] <= datetime.now(timezone.utc):
            raise HTTPException(409, "Audio expired; transcript can no longer be checked")
        previous = conn.execute(
            """SELECT id,raw_text,text_version FROM extracted_passage
               WHERE document_id=%s AND page_number=1 ORDER BY text_version DESC LIMIT 1""",
            (document_id,),
        ).fetchone()
        if not previous:
            raise HTTPException(409, "Transcription has not finished")
        if corrected == previous["raw_text"]:
            raise HTTPException(422, "Corrected transcript is unchanged")
        passage_id = uuid4()
        conn.execute(
            """INSERT INTO extracted_passage
               (id,document_id,page_number,raw_text,ocr_applied,text_version,
                transcription_language)
               VALUES (%s,%s,1,%s,false,%s,%s)""",
            (passage_id, document_id, corrected, previous["text_version"] + 1,
             memo["language"]),
        )
        conn.execute(
            """UPDATE document_event_draft SET state='rejected',version=version+1
               WHERE document_id=%s AND state='needs_review'""", (document_id,),
        )
        context = normalization_context(conn, conn.execute(
            "SELECT wellbore_id FROM document_wellbore WHERE document_id=%s",
            (document_id,),
        ).fetchone()["wellbore_id"])
        for candidate in local_candidates(corrected):
            normalized, issues = normalize(candidate, context)
            issues.append("voice_transcript_verify")
            fields = Jsonb(candidate.model_dump())
            conn.execute(
                """INSERT INTO document_event_draft
                   (id,document_id,passage_id,original_fields,current_fields,normalized_fields,issues)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (uuid4(), document_id, passage_id, fields, fields,
                 Jsonb(normalized), Jsonb(issues)),
            )
        conn.execute(
            """UPDATE source_document SET review_version=review_version+1,
               ingest_status='needs_review' WHERE id=%s""", (document_id,),
        )
        append_decision(
            conn, actor=principal.name, action="voice_transcript_corrected",
            entity_type="source_document", entity_id=document_id,
            payload={"old_passage_id": str(previous["id"]),
                     "new_passage_id": str(passage_id),
                     "old_text_sha256": text_digest(previous["raw_text"]),
                     "new_text_sha256": text_digest(corrected),
                     "rationale_sha256": text_digest(body.rationale)},
        )
        return save_receipt(conn, principal.name, idempotency_key, digest,
                            {"passage_id": str(passage_id),
                             "text_version": previous["text_version"] + 1})


@router.get("/documents/{document_id}/pages/{page_id}/preview")
def preview(document_id: UUID, page_id: UUID, _principal=Depends(require_role("reviewer"))):
    with connection() as conn:
        row = conn.execute(
            "SELECT preview_key FROM extracted_passage WHERE document_id=%s AND id=%s",
            (document_id, page_id),
        ).fetchone()
    if not row or not row["preview_key"]:
        raise HTTPException(404, "Preview unavailable")
    return FileResponse(
        path_for(row["preview_key"]), media_type="image/png", headers={"Cache-Control": "no-store"}
    )


@router.post("/documents/{document_id}/retry", status_code=202)
def retry(
    document_id: UUID,
    idempotency_key: str = Header(...),
    principal=Depends(require_role("reviewer")),
):
    with connection() as conn:
        digest, old = receipt(conn, principal.name, idempotency_key, ["retry", document_id])
        if old:
            return old
        document = conn.execute(
            "SELECT * FROM source_document WHERE id=%s FOR UPDATE", (document_id,)
        ).fetchone()
        if not document:
            raise HTTPException(404, "Document not found")
        if document["ingest_status"] != "failed":
            raise HTTPException(409, "Only failed documents can be retried")
        generation = document["extraction_generation"] + 1
        conn.execute(
            "UPDATE source_document SET ingest_status='pending',extraction_generation=%s WHERE id=%s",
            (generation, document_id),
        )
        conn.execute(
            "INSERT INTO ingestion_job(id,document_id,stage,generation) VALUES(%s,%s,'extract',%s)",
            (uuid4(), document_id, generation),
        )
        return save_receipt(conn, principal.name, idempotency_key, digest, {"id": str(document_id)})


@router.post("/documents/{document_id}/review")
def review(
    document_id: UUID,
    body: ReviewRequest,
    idempotency_key: str = Header(...),
    principal=Depends(require_role("reviewer")),
):
    with connection() as conn:
        digest, old = receipt(
            conn, principal.name, idempotency_key, ["review", document_id, body.model_dump()]
        )
        if old:
            return old
        document = conn.execute("SELECT * FROM source_document WHERE id=%s FOR UPDATE",
                                (document_id,)).fetchone()
        if not document:
            raise HTTPException(404, "Document not found")
        if body.decision == "approve":
            if document["doc_type"] == "voice_memo":
                if principal.name == document["uploaded_by"]:
                    raise HTTPException(409, "A different reviewer must verify this voice memo")
                if not body.voice_audio_verified:
                    raise HTTPException(422, "Listen to the audio and explicitly verify the transcript")
                memo = conn.execute(
                    "SELECT audio_retention_until,audio_purged_at FROM voice_memo WHERE document_id=%s",
                    (document_id,),
                ).fetchone()
                if (not memo or memo["audio_purged_at"]
                        or memo["audio_retention_until"] <= datetime.now(timezone.utc)):
                    raise HTTPException(409, "Voice audio expired before verification")
            dataset = conn.execute(
                """SELECT d.kind,d.qualification_status,d.origin_kind,d.authorization_state,d.applicability
                FROM source_document s
                JOIN dataset d ON d.id=s.dataset_id WHERE s.id=%s""",
                (document_id,),
            ).fetchone()
            if not dataset or not may_approve_event(dataset):
                raise HTTPException(409, "Source provenance does not permit event approval")
        draft = conn.execute(
            "SELECT * FROM document_event_draft WHERE id=%s AND document_id=%s FOR UPDATE",
            (body.candidate_id, document_id),
        ).fetchone()
        if not draft:
            raise HTTPException(404, "Candidate not found")
        if draft["version"] != body.expected_version or draft["state"] != "needs_review":
            raise HTTPException(
                409, "Evidence changed or was already finalized; refresh before reviewing"
            )
        fields = body.fields or Candidate.model_validate(draft["current_fields"])
        passage = conn.execute(
            "SELECT raw_text,ocr_applied FROM extracted_passage WHERE id=%s", (draft["passage_id"],)
        ).fetchone()
        if not quote_is_supported(fields.quote, passage["raw_text"]):
            raise HTTPException(422, "Quote must match text on the source page")
        wellbore = conn.execute(
            "SELECT wellbore_id FROM document_wellbore WHERE document_id=%s", (document_id,)
        ).fetchone()["wellbore_id"]
        normalized, issues = normalize(fields, normalization_context(conn, wellbore))
        if passage["ocr_applied"]:
            issues.append("ocr_source_verify")
        if body.decision == "approve" and issues and not body.acknowledge_issues:
            raise HTTPException(422, "Unresolved quality issues require explicit acknowledgment")
        state = {"approve": "approved", "reject": "rejected", "correct": "needs_review"}[
            body.decision
        ]
        event_id = None
        if state == "approved":
            event_id = uuid4()
            conn.execute(
                """INSERT INTO drilling_event(id,wellbore_id,formation_interval_id,event_type,start_md_m,
                end_md_m,severity,description,review_state,extraction_run_id,source_depth_axis,source_depth_unit,
                source_datum,source_fields,quality_issues,onset_time_earliest,onset_time_latest,
                onset_time_basis) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'approved',%s,%s,%s,%s,%s,%s,
                %s,%s,%s)""",
                (
                    event_id,
                    wellbore,
                    normalized["formation_interval_id"],
                    fields.event_type,
                    normalized["start_md_m"],
                    normalized["end_md_m"],
                    fields.severity,
                    fields.description,
                    draft["run_id"],
                    fields.depth_axis,
                    fields.depth_unit,
                    fields.depth_datum,
                    Jsonb(fields.model_dump()),
                    Jsonb(issues),
                    body.onset.earliest,
                    body.onset.latest,
                    body.onset.basis,
                ),
            )
            conn.execute(
                "INSERT INTO event_passage(event_id,passage_id) VALUES(%s,%s)",
                (event_id, draft["passage_id"]),
            )
            if fields.mitigation:
                conn.execute(
                    "INSERT INTO mitigation(id,event_id,action_taken,effectiveness) VALUES(%s,%s,%s,%s)",
                    (uuid4(), event_id, fields.mitigation, fields.outcome),
                )
            if fields.outcome:
                conn.execute(
                    "INSERT INTO event_outcome(id,event_id,outcome) VALUES(%s,%s,%s)",
                    (uuid4(), event_id, fields.outcome),
                )
            if normalized["npt_hours"] is not None:
                conn.execute(
                    "INSERT INTO npt_event(id,event_id,duration_h,duration_source) VALUES(%s,%s,%s,'reviewed report')",
                    (uuid4(), event_id, normalized["npt_hours"]),
                )
        conn.execute(
            """UPDATE document_event_draft SET current_fields=%s,normalized_fields=%s,issues=%s,
            state=%s,version=version+1,canonical_event_id=%s WHERE id=%s""",
            (
                Jsonb(fields.model_dump()),
                Jsonb(normalized),
                Jsonb(issues),
                state,
                event_id,
                draft["id"],
            ),
        )
        review_id = uuid4()
        conn.execute(
            """INSERT INTO review_decision(id,entity_type,entity_id,entity_version,actor_name,action,
            rationale,before_value,after_value,document_id) VALUES(%s,'document_event_draft',%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                review_id,
                draft["id"],
                draft["version"] + 1,
                principal.name,
                body.decision,
                body.rationale,
                Jsonb(draft["current_fields"]),
                Jsonb(fields.model_dump() | {"_onset_review": body.onset.model_dump(mode="json")}),
                document_id,
            ),
        )
        append_decision(
            conn,
            actor=principal.name,
            action=f"review_{body.decision}",
            entity_type="document_event_draft",
            entity_id=draft["id"],
            payload={"review_decision_id": str(review_id), "document_id": str(document_id),
                     "version": draft["version"] + 1, "event_id": str(event_id) if event_id else None,
                     "rationale_sha256": text_digest(body.rationale)},
        )
        conn.execute(
            """UPDATE source_document SET review_version=review_version+1,ingest_status=CASE WHEN
            EXISTS(SELECT 1 FROM document_event_draft WHERE document_id=%s AND state='needs_review')
            THEN 'needs_review' ELSE 'reviewed' END WHERE id=%s""",
            (document_id, document_id),
        )
        return save_receipt(
            conn,
            principal.name,
            idempotency_key,
            digest,
            {"state": state, "version": draft["version"] + 1},
        )


@router.post("/documents/{document_id}/candidates", status_code=201)
def manual_candidate(
    document_id: UUID,
    body: ManualCandidateRequest,
    idempotency_key: str = Header(...),
    principal=Depends(require_role("reviewer")),
):
    with connection() as conn:
        digest, old = receipt(
            conn, principal.name, idempotency_key, ["manual", document_id, body.model_dump()]
        )
        if old:
            return old
        document = conn.execute(
            "SELECT * FROM source_document WHERE id=%s FOR UPDATE", (document_id,)
        ).fetchone()
        if not document:
            raise HTTPException(404, "Document not found")
        if document["review_version"] != body.expected_version or document["ingest_status"] not in (
            "needs_review",
            "reviewed",
        ):
            raise HTTPException(409, "Document changed or is not ready for review; refresh first")
        page = conn.execute(
            "SELECT * FROM extracted_passage WHERE document_id=%s AND page_number=%s ORDER BY text_version DESC LIMIT 1",
            (document_id, body.page_number),
        ).fetchone()
        if not page or not quote_is_supported(body.fields.quote, page["raw_text"]):
            raise HTTPException(422, "Quote must match text on the selected source page")
        wellbore = conn.execute(
            "SELECT wellbore_id FROM document_wellbore WHERE document_id=%s", (document_id,)
        ).fetchone()["wellbore_id"]
        normalized, issues = normalize(body.fields, normalization_context(conn, wellbore))
        if page["ocr_applied"]:
            issues.append("ocr_source_verify")
        candidate_id = uuid4()
        fields = Jsonb(body.fields.model_dump())
        conn.execute(
            """INSERT INTO document_event_draft(id,document_id,passage_id,original_fields,current_fields,
            normalized_fields,issues) VALUES(%s,%s,%s,%s,%s,%s,%s)""",
            (
                candidate_id,
                document_id,
                page["id"],
                fields,
                fields,
                Jsonb(normalized),
                Jsonb(issues),
            ),
        )
        review_id = uuid4()
        conn.execute(
            """INSERT INTO review_decision(id,entity_type,entity_id,entity_version,actor_name,action,
            rationale,after_value,document_id) VALUES(%s,'document_event_draft',%s,1,%s,'manual_create',%s,%s,%s)""",
            (review_id, candidate_id, principal.name, body.rationale, fields, document_id),
        )
        append_decision(
            conn,
            actor=principal.name,
            action="review_manual_create",
            entity_type="document_event_draft",
            entity_id=candidate_id,
            payload={"review_decision_id": str(review_id), "document_id": str(document_id),
                     "page_number": body.page_number,
                     "rationale_sha256": text_digest(body.rationale)},
        )
        conn.execute(
            "UPDATE source_document SET review_version=review_version+1,ingest_status='needs_review' WHERE id=%s",
            (document_id,),
        )
        return save_receipt(
            conn, principal.name, idempotency_key, digest, {"id": str(candidate_id)}
        )
