"""Reviewer-curated, page-cited report facts. Never searches unreviewed OCR."""

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from nwis.db import connection
from nwis.decision_ledger import append_decision, text_digest
from nwis.ingestion.extract import quote_is_supported
from nwis.provenance import may_approve_event
from nwis.security import current_principal, require_role

router = APIRouter(prefix="/api/v1/report-facts")


class ReviewFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: UUID
    passage_id: UUID
    fact_key: str = Field(min_length=3, max_length=120, pattern=r"^[a-z][a-z0-9_]*$")
    answer: str = Field(min_length=1, max_length=1000)
    quote: str = Field(min_length=1, max_length=4000)
    rationale: str = Field(min_length=3, max_length=2000)
    ocr_image_verified: bool = False


class AskFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: UUID
    fact_key: str = Field(min_length=3, max_length=120, pattern=r"^[a-z][a-z0-9_]*$")


class ReviewQuestion(AskFact):
    question: str = Field(min_length=5, max_length=500)
    state: str = Field(pattern="^(ready|conflict_blocked)$")
    reason: str | None = Field(default=None, max_length=1000)


class AskQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_id: UUID


@router.post("", status_code=201)
def approve_fact(body: ReviewFact, principal=Depends(require_role("reviewer"))):
    with connection() as conn:
        row = conn.execute(
            """SELECT p.raw_text,p.text_version,p.page_number,p.ocr_applied,
                sd.id AS document_id,sd.dataset_id,d.kind,d.origin_kind,
                d.authorization_state,d.applicability,d.qualification_status
                FROM extracted_passage p JOIN source_document sd ON sd.id=p.document_id
                JOIN dataset d ON d.id=sd.dataset_id WHERE p.id=%s FOR SHARE OF p,sd,d""",
            (body.passage_id,),
        ).fetchone()
        if not row or row["dataset_id"] != body.dataset_id:
            raise HTTPException(422, "Passage does not belong to this dataset")
        if not may_approve_event(row):
            raise HTTPException(409, "Dataset is not qualified for approved evidence")
        if not body.answer.strip() or not body.quote.strip():
            raise HTTPException(422, "Answer and quote cannot be blank")
        if len(body.rationale.strip()) < 3:
            raise HTTPException(422, "A review rationale is required")
        if not quote_is_supported(body.quote, row["raw_text"]):
            raise HTTPException(422, "Quote must occur in the cited passage")
        if row["ocr_applied"] and not body.ocr_image_verified:
            raise HTTPException(422, "OCR facts require explicit page-image verification")
        fact_id = uuid4()
        conn.execute(
            """INSERT INTO reviewed_report_fact
                (id,dataset_id,passage_id,fact_key,answer,quote,reviewer_name,
                 review_rationale,ocr_image_verified)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                fact_id,
                body.dataset_id,
                body.passage_id,
                body.fact_key,
                body.answer.strip(),
                body.quote.strip(),
                principal.name,
                body.rationale.strip(),
                body.ocr_image_verified,
            ),
        )
        append_decision(
            conn,
            actor=principal.name,
            action="approve_report_fact",
            entity_type="report_fact",
            entity_id=fact_id,
            payload={
                "dataset_id": str(body.dataset_id),
                "passage_id": str(body.passage_id),
                "text_version": row["text_version"],
                "fact_key": body.fact_key,
                "answer_sha256": text_digest(body.answer.strip()),
                "quote_sha256": text_digest(body.quote.strip()),
                "rationale_sha256": text_digest(body.rationale.strip()),
                "ocr_image_verified": body.ocr_image_verified,
            },
        )
        return {
            "id": fact_id,
            "state": "approved",
            "page_number": row["page_number"],
            "ocr_applied": row["ocr_applied"],
        }


@router.post("/{fact_id}/withdraw")
def withdraw_fact(fact_id: UUID, principal=Depends(require_role("reviewer"))):
    with connection() as conn:
        row = conn.execute(
            "SELECT id,state,dataset_id,passage_id FROM reviewed_report_fact WHERE id=%s FOR UPDATE",
            (fact_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Report fact not found")
        if row["state"] != "approved":
            raise HTTPException(409, "Report fact is already withdrawn")
        conn.execute("UPDATE reviewed_report_fact SET state='withdrawn' WHERE id=%s", (fact_id,))
        append_decision(
            conn,
            actor=principal.name,
            action="withdraw_report_fact",
            entity_type="report_fact",
            entity_id=fact_id,
            payload={"dataset_id": str(row["dataset_id"]), "passage_id": str(row["passage_id"])},
        )
        return {"id": fact_id, "state": "withdrawn"}


@router.get("/documents/{document_id}")
def document_facts(document_id: UUID, principal=Depends(current_principal)):
    with connection() as conn:
        document = conn.execute(
            """SELECT sd.dataset_id,sd.uploaded_by,d.* FROM source_document sd
                JOIN dataset d ON d.id=sd.dataset_id WHERE sd.id=%s""",
            (document_id,),
        ).fetchone()
        if not document:
            raise HTTPException(404, "Document not found")
        reviewer = principal.role in ("reviewer", "admin")
        if not reviewer and not may_approve_event(document):
            return []
        return conn.execute(
            """SELECT f.id,f.fact_key,f.answer,f.quote,f.state,f.reviewer_name,f.reviewed_at,
                f.review_rationale,f.ocr_image_verified,p.page_number,p.id AS passage_id FROM reviewed_report_fact f
                JOIN extracted_passage p ON p.id=f.passage_id WHERE p.document_id=%s
                AND (%s OR f.state='approved')
                ORDER BY f.reviewed_at DESC,f.id LIMIT 200""",
            (document_id, reviewer),
        ).fetchall()


@router.post("/questions", status_code=201)
def add_question(body: ReviewQuestion, principal=Depends(require_role("reviewer"))):
    if body.state == "conflict_blocked" and not (body.reason or "").strip():
        raise HTTPException(422, "A blocked question needs a reason")
    with connection() as conn:
        dataset = conn.execute("SELECT * FROM dataset WHERE id=%s", (body.dataset_id,)).fetchone()
        if not dataset:
            raise HTTPException(404, "Dataset not found")
        if body.state == "ready" and not may_approve_event(dataset):
            raise HTTPException(409, "Dataset is not qualified for ready questions")
        if (
            body.state == "ready"
            and not conn.execute(
                """SELECT 1 FROM reviewed_report_fact WHERE dataset_id=%s AND fact_key=%s
                AND state='approved' LIMIT 1""",
                (body.dataset_id, body.fact_key),
            ).fetchone()
        ):
            raise HTTPException(409, "Ready questions require an approved report fact")
        question_id = uuid4()
        conn.execute(
            """INSERT INTO report_fact_question
                (id,dataset_id,fact_key,question,state,reason,reviewer_name)
                VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (
                question_id,
                body.dataset_id,
                body.fact_key,
                body.question.strip(),
                body.state,
                body.reason.strip() if body.reason else None,
                principal.name,
            ),
        )
        append_decision(
            conn,
            actor=principal.name,
            action="register_report_question",
            entity_type="report_fact_question",
            entity_id=question_id,
            payload={
                "dataset_id": str(body.dataset_id),
                "fact_key": body.fact_key,
                "state": body.state,
                "question_sha256": text_digest(body.question.strip()),
                "reason_sha256": text_digest(body.reason.strip()) if body.reason else None,
            },
        )
        return {"id": question_id, "state": body.state}


@router.get("/questions")
def questions(dataset_id: UUID | None = None, _principal=Depends(current_principal)):
    with connection() as conn:
        if (
            dataset_id
            and not conn.execute("SELECT 1 FROM dataset WHERE id=%s", (dataset_id,)).fetchone()
        ):
            raise HTTPException(404, "Dataset not found")
        return conn.execute(
            """SELECT q.id,q.dataset_id,q.question,q.state,q.reason,q.created_at,
                d.kind,d.qualification_status,d.applicability
                FROM report_fact_question q JOIN dataset d ON d.id=q.dataset_id
                WHERE (%s::uuid IS NULL OR q.dataset_id=%s)
                ORDER BY q.created_at,q.id LIMIT 100""",
            (dataset_id, dataset_id),
        ).fetchall()


@router.post("/ask-question")
def ask_question(body: AskQuestion, principal=Depends(current_principal)):
    with connection() as conn:
        item = conn.execute(
            "SELECT id,dataset_id,fact_key,question,state,reason FROM report_fact_question WHERE id=%s",
            (body.question_id,),
        ).fetchone()
    if not item:
        raise HTTPException(404, "Question not found")
    if item["state"] == "conflict_blocked":
        return {
            "question": item["question"],
            "status": "conflict",
            "answer": None,
            "citations": [],
            "reason": item["reason"],
        }
    answer = ask_fact(AskFact(dataset_id=item["dataset_id"], fact_key=item["fact_key"]), principal)
    return {"question": item["question"], **answer}


@router.post("/ask")
def ask_fact(body: AskFact, _principal=Depends(current_principal)):
    with connection() as conn:
        dataset = conn.execute("SELECT * FROM dataset WHERE id=%s", (body.dataset_id,)).fetchone()
        if not dataset:
            raise HTTPException(404, "Dataset not found")
        if not may_approve_event(dataset):
            return {
                "status": "no_answer",
                "answer": None,
                "citations": [],
                "reason": "dataset_not_qualified",
            }
        rows = conn.execute(
            """SELECT f.id,f.answer,f.quote,f.reviewer_name,f.reviewed_at,
                f.ocr_image_verified,p.id AS passage_id,p.page_number,p.text_version,p.ocr_applied,
                sd.id AS document_id,sd.filename,sd.version AS document_version
                FROM reviewed_report_fact f JOIN extracted_passage p ON p.id=f.passage_id
                JOIN source_document sd ON sd.id=p.document_id
                WHERE f.dataset_id=%s AND f.fact_key=%s AND f.state='approved'
                ORDER BY f.reviewed_at,f.id LIMIT 101""",
            (body.dataset_id, body.fact_key),
        ).fetchall()
    if not rows:
        return {
            "status": "no_answer",
            "answer": None,
            "citations": [],
            "reason": "no_reviewed_fact",
        }
    answers = {row["answer"].strip().casefold() for row in rows}
    if len(answers) != 1 or len(rows) > 100:
        return {
            "status": "conflict",
            "answer": None,
            "citations": rows[:100],
            "reason": "disputed_or_overfull_evidence",
        }
    return {
        "status": "answered",
        "answer": rows[0]["answer"],
        "citations": rows,
        "reason": None,
        "answer_kind": "reviewer_curated_fact",
    }


class RagQueryRequest(BaseModel):
    dataset_id: UUID
    question: str = Field(min_length=2, max_length=500)
    wellbore_id: UUID | None = None


@router.post("/query-rag")
def ask_rag_endpoint(body: RagQueryRequest, _principal=Depends(current_principal)):
    with connection() as conn:
        from nwis.rag_engine import query_rag_engine
        return query_rag_engine(conn, body.dataset_id, body.question, body.wellbore_id)

