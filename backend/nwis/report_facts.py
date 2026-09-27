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


class AskFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: UUID
    fact_key: str = Field(min_length=3, max_length=120, pattern=r"^[a-z][a-z0-9_]*$")


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
        if not quote_is_supported(body.quote, row["raw_text"]):
            raise HTTPException(422, "Quote must occur in the cited passage")
        fact_id = uuid4()
        conn.execute(
            """INSERT INTO reviewed_report_fact
                (id,dataset_id,passage_id,fact_key,answer,quote,reviewer_name)
                VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (
                fact_id,
                body.dataset_id,
                body.passage_id,
                body.fact_key,
                body.answer.strip(),
                body.quote.strip(),
                principal.name,
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
                p.id AS passage_id,p.page_number,p.text_version,p.ocr_applied,
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
