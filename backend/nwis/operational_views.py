"""Cited, read-only operational summaries and a non-authoritative Assam name aid."""

import re
from collections import Counter
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from nwis.db import connection
from nwis.exploration import permitted_dataset
from nwis.security import current_principal

router = APIRouter(prefix="/api/v1")

# Names are taken from OIL's regional sequence, not from a reviewed well report.
# Do not use these suggestions as formation intervals or as hazard/depth assertions.
ASSAM_SOURCE = "https://www.oil-india.com/files/oldtender/global/NIT_CDG1116P20.pdf"
ASSAM_FORMATIONS = (
    ("sylhet", "Sylhet Group", ("Sylhet", "Sylhet Group")),
    ("kopili", "Kopili", ("Kopili", "Kopili Formation")),
    ("barail", "Barail", ("Barail", "Barail Formation")),
    ("tipam", "Tipam", ("Tipam", "Tipam Formation")),
    ("girujan", "Girujan", ("Girujan", "Girujan Formation")),
    ("namsang", "Namsang", ("Namsang", "Namsang Formation")),
    ("siwalik_dhekiajuli", "Siwalik / Dhekiajuli", ("Siwalik", "Dhekiajuli")),
)


def name_key(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.casefold())).strip()


def suggest_assam_formation(value: str) -> dict | None:
    key = name_key(value)
    if not key:
        return None
    for code, name, aliases in ASSAM_FORMATIONS:
        if key in {name_key(alias) for alias in aliases}:
            return {"code": code, "name": name, "matched_alias": value.strip(),
                    "source_url": ASSAM_SOURCE, "status": "reference_suggestion_only"}
    return None


@router.get("/reference/assam-formations")
def assam_formations(_principal=Depends(current_principal)):
    return {"source_url": ASSAM_SOURCE, "status": "reference_suggestion_only",
            "notice": "Regional names only. Dataset-scoped aliases and well intervals require review.",
            "items": [{"code": code, "name": name, "aliases": aliases}
                      for code, name, aliases in ASSAM_FORMATIONS]}


class FormationSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)


@router.post("/reference/assam-formations/suggest")
def formation_suggestion(body: FormationSuggestion, _principal=Depends(current_principal)):
    return {"suggestion": suggest_assam_formation(body.name),
            "notice": "Exact regional-name match only; no automatic formation approval."}


def _cited_events(conn, dataset_id: UUID, event_types: tuple[str, ...] | None = None):
    return conn.execute(
        """SELECT e.id, e.event_type, e.start_md_m,
                  COALESCE(f.display_name,'Formation unrecorded') AS formation_name,
                  fo.outcome AS fishing_outcome, fo.duration_h AS fishing_duration_h,
                  (SELECT o.outcome FROM event_outcome o WHERE o.event_id=e.id
                   ORDER BY o.id LIMIT 1) AS reported_outcome
           FROM drilling_event e JOIN wellbore b ON b.id=e.wellbore_id
           JOIN well w ON w.id=b.well_id
           LEFT JOIN formation_interval fi ON fi.id=e.formation_interval_id
           LEFT JOIN formation f ON f.id=fi.formation_id
           LEFT JOIN fishing_operation fo ON fo.event_id=e.id
           WHERE w.dataset_id=%s AND e.review_state='approved'
             AND e.quality_issues='[]'::jsonb
             AND EXISTS(SELECT 1 FROM event_passage ep WHERE ep.event_id=e.id)
             AND (%s::text[] IS NULL OR e.event_type=ANY(%s::text[]))
           ORDER BY e.id LIMIT 201""",
        (dataset_id, list(event_types) if event_types else None,
         list(event_types) if event_types else None),
    ).fetchall()


@router.get("/knowledge/special-operations")
def special_operations(dataset_id: UUID, _principal=Depends(current_principal)):
    with connection() as conn:
        dataset = permitted_dataset(conn, dataset_id)
        rows = _cited_events(conn, dataset_id, ("fishing", "cementing_issue"))
    items = []
    for event_type in ("fishing", "cementing_issue"):
        subset = [row for row in rows[:200] if row["event_type"] == event_type]
        outcomes = Counter((row["fishing_outcome"] if event_type == "fishing" else None)
                           or row["reported_outcome"] or "unknown" for row in subset)
        items.append({"event_type": event_type, "sample_count": len(subset),
                      "state": "descriptive" if len(subset) >= 3 and len(rows) <= 200 else "insufficient",
                      "outcome_counts": dict(outcomes) if len(subset) >= 3 and len(rows) <= 200 else {},
                      "cases": [{"event_id": row["id"], "formation_name": row["formation_name"],
                                 "start_md_m": row["start_md_m"],
                                 "duration_h": row["fishing_duration_h"] if event_type == "fishing" else None}
                                for row in subset]})
    return {"source_kind": dataset["kind"], "items": items, "truncated": len(rows) > 200,
            "notice": "Approved cited reports only. Counts describe reported outcomes, not success rates or drilling advice. Below n=3, distributions are withheld."}


class ExposureInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    dataset_id: UUID
    rig_day_rate: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: str = Field(pattern=r"^[A-Z]{3}$")


@router.post("/knowledge/npt-exposure")
def npt_exposure(body: ExposureInput, _principal=Depends(current_principal)):
    with connection() as conn:
        dataset = permitted_dataset(conn, body.dataset_id)
        rows = conn.execute(
            """SELECT n.id AS npt_id, e.id AS event_id, e.event_type,
                      COALESCE(f.display_name,'Formation unrecorded') AS formation_name,
                      n.duration_h, n.duration_source
               FROM npt_event n JOIN drilling_event e ON e.id=n.event_id
               JOIN wellbore b ON b.id=e.wellbore_id JOIN well w ON w.id=b.well_id
               LEFT JOIN formation_interval fi ON fi.id=e.formation_interval_id
               LEFT JOIN formation f ON f.id=fi.formation_id
               WHERE w.dataset_id=%s AND e.review_state='approved'
                 AND e.quality_issues='[]'::jsonb
                 AND EXISTS(SELECT 1 FROM event_passage ep WHERE ep.event_id=e.id)
               ORDER BY n.id LIMIT 201""", (body.dataset_id,),
        ).fetchall()
    items = []
    for row in rows[:200]:
        duration = Decimal(str(row["duration_h"]))
        items.append({"npt_id": row["npt_id"], "event_id": row["event_id"], "event_type": row["event_type"],
                      "formation_name": row["formation_name"],
                      "duration_h": duration, "duration_source": row["duration_source"],
                      "illustrative_exposure": (duration * body.rig_day_rate / 24).quantize(Decimal("0.01"))})
    return {"source_kind": dataset["kind"], "currency": body.currency,
            "assumed_rig_day_rate": body.rig_day_rate, "items": items,
            "truncated": len(rows) > 200, "total": None,
            "notice": "Illustrative historical duration × user-assumed rig-day rate / 24, per episode only. Episodes may overlap; no total, proven savings, or causal claim."}
