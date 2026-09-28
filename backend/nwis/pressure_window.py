"""Cited pressure/mud bands for visual comparison, never a mud-weight recommendation."""

from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from psycopg.errors import CheckViolation, ForeignKeyViolation

from nwis.db import connection
from nwis.decision_ledger import append_decision, text_digest
from nwis.ingestion.api import receipt, save_receipt
from nwis.intelligence import bore
from nwis.provenance import may_approve_event
from nwis.security import current_principal, require_role

router = APIRouter(prefix="/api/v1")


class PressureBand(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    wellbore_id: UUID
    formation_interval_id: UUID
    top_md_m: float = Field(ge=0)
    base_md_m: float = Field(gt=0)
    pore_pressure_ppg: float = Field(gt=0)
    fracture_gradient_ppg: float = Field(gt=0)
    mud_weight_ppg: float = Field(gt=0)
    ecd_ppg: float | None = Field(default=None, gt=0)
    pressure_passage_id: UUID
    mud_passage_id: UUID

    @model_validator(mode="after")
    def physical_order(self):
        if self.base_md_m <= self.top_md_m:
            raise ValueError("Depth band must have positive length")
        if self.fracture_gradient_ppg <= self.pore_pressure_ppg:
            raise ValueError("Fracture gradient must exceed pore pressure")
        return self


class PressureDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]
    rationale: str = Field(min_length=3, max_length=2000)


@router.post("/pressure-windows", status_code=201)
def stage_pressure_band(
    body: PressureBand, idempotency_key: str = Header(...),
    principal=Depends(require_role("engineer", "reviewer")),
):
    try:
        with connection() as conn:
            digest, old = receipt(conn, principal.name, idempotency_key,
                                  ["stage_pressure_band", body.model_dump(mode="json")])
            if old:
                return old
            band_id = uuid4()
            conn.execute(
                """INSERT INTO pressure_window_evidence
                   (id,wellbore_id,formation_interval_id,top_md_m,base_md_m,
                    pore_pressure_ppg,fracture_gradient_ppg,mud_weight_ppg,ecd_ppg,
                    pressure_passage_id,mud_passage_id,prepared_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (band_id, body.wellbore_id, body.formation_interval_id,
                 body.top_md_m, body.base_md_m, body.pore_pressure_ppg,
                 body.fracture_gradient_ppg, body.mud_weight_ppg, body.ecd_ppg,
                 body.pressure_passage_id, body.mud_passage_id, principal.name),
            )
            append_decision(conn, actor=principal.name, action="pressure_band_staged",
                            entity_type="pressure_window_evidence", entity_id=band_id,
                            payload={"wellbore_id": str(body.wellbore_id),
                                     "pressure_passage_id": str(body.pressure_passage_id),
                                     "mud_passage_id": str(body.mud_passage_id)})
            return save_receipt(conn, principal.name, idempotency_key, digest,
                                {"id": str(band_id), "review_state": "staged"})
    except (CheckViolation, ForeignKeyViolation) as exc:
        raise HTTPException(422, "Band needs a reviewed formation and linked source passages") from exc


@router.post("/pressure-windows/{band_id}/review")
def review_pressure_band(
    band_id: UUID, body: PressureDecision, idempotency_key: str = Header(...),
    principal=Depends(require_role("reviewer")),
):
    try:
        with connection() as conn:
            digest, old = receipt(conn, principal.name, idempotency_key,
                                  ["review_pressure_band", band_id, body.model_dump()])
            if old:
                return old
            row = conn.execute("SELECT * FROM pressure_window_evidence WHERE id=%s FOR UPDATE",
                               (band_id,)).fetchone()
            if not row:
                raise HTTPException(404, "Pressure band not found")
            if row["review_state"] != "staged":
                raise HTTPException(409, "Pressure band already reviewed")
            if row["prepared_by"] == principal.name:
                raise HTTPException(409, "A different reviewer must check these values")
            state = "approved" if body.decision == "approve" else "rejected"
            conn.execute(
                """UPDATE pressure_window_evidence SET review_state=%s,reviewed_by=%s,
                   review_reference=%s,reviewed_at=now() WHERE id=%s""",
                (state, principal.name, body.rationale, band_id),
            )
            append_decision(conn, actor=principal.name, action=f"pressure_band_{state}",
                            entity_type="pressure_window_evidence", entity_id=band_id,
                            payload={"state": state,
                                     "rationale_sha256": text_digest(body.rationale)})
            return save_receipt(conn, principal.name, idempotency_key, digest,
                                {"id": str(band_id), "review_state": state})
    except CheckViolation as exc:
        raise HTTPException(422, "Band is unqualified, overlaps another approved band, or lacks citations") from exc


@router.get("/wellbores/{wellbore_id}/mud-window")
def mud_window(wellbore_id: UUID, _principal=Depends(current_principal)):
    with connection() as conn:
        identity = bore(conn, wellbore_id)
        eligible = may_approve_event({**identity, "kind": identity["data_kind"]})
        rows = conn.execute(
            """SELECT p.id,p.top_md_m,p.base_md_m,p.pore_pressure_ppg,
                      p.fracture_gradient_ppg,p.mud_weight_ppg,p.ecd_ppg,
                      p.formation_interval_id,p.reviewed_by,p.reviewed_at,
                      p.pressure_passage_id,p.mud_passage_id,
                      dp.filename AS pressure_filename,pp.page_number AS pressure_page,
                      dm.filename AS mud_filename,pm.page_number AS mud_page
               FROM pressure_window_evidence p
               JOIN extracted_passage pp ON pp.id=p.pressure_passage_id
               JOIN source_document dp ON dp.id=pp.document_id
               JOIN extracted_passage pm ON pm.id=p.mud_passage_id
               JOIN source_document dm ON dm.id=pm.document_id
               WHERE p.wellbore_id=%s AND p.review_state='approved'
               ORDER BY p.top_md_m,p.id LIMIT 201""", (wellbore_id,)
        ).fetchall() if eligible else []
    return {"wellbore_id": str(wellbore_id), "source_kind": identity["data_kind"],
            "state": "available" if rows else "unavailable", "bands": rows[:200],
            "truncated": len(rows) > 200, "unit": "ppg",
            "notice": "Cited historical measurements/program values, not a safe mud-weight window or operating recommendation. ECD is shown only when separately reviewed."}
