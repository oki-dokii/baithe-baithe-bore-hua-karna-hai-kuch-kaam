"""Read-only planning and evidence views; no risk probability or drilling advice."""

from collections import Counter, defaultdict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from nwis.db import connection
from nwis.drilling_parameters import eligible_anchors
from nwis.intelligence import bore, interval_rows
from nwis.provenance import may_approve_event
from nwis.security import current_principal

router = APIRouter(prefix="/api/v1")


class PlanningPoint(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    dataset_id: UUID
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_km: float = Field(default=5, ge=0.1, le=100)
    formation_id: UUID | None = None
    min_md_m: float | None = Field(default=None, ge=0)
    max_md_m: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def ordered_depth(self):
        if (self.min_md_m is not None and self.max_md_m is not None
                and self.min_md_m > self.max_md_m):
            raise ValueError("Depth range is reversed")
        return self


def permitted_dataset(conn, dataset_id: UUID) -> dict:
    row = conn.execute(
        """SELECT kind,origin_kind,authorization_state,applicability,
                  qualification_status FROM dataset WHERE id=%s""", (dataset_id,)
    ).fetchone()
    if not row or not may_approve_event(row):
        raise HTTPException(422, "Dataset is not qualified for approved evidence views")
    return row


@router.post("/planning/offset-picture")
def offset_picture(body: PlanningPoint, _principal=Depends(current_principal)):
    with connection() as conn:
        dataset = permitted_dataset(conn, body.dataset_id)
        wells = conn.execute(
            """SELECT w.id AS well_id,b.id AS wellbore_id,w.name,
                      ST_X(w.surface_point::geometry) AS longitude,
                      ST_Y(w.surface_point::geometry) AS latitude,
                      ST_Distance(w.surface_point,
                          ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography) AS distance_m
               FROM well w JOIN wellbore b ON b.well_id=w.id
               WHERE w.dataset_id=%s AND w.status<>'benchmark_unlocated'
                 AND ST_DWithin(w.surface_point,
                     ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography,%s)
               ORDER BY distance_m,b.id LIMIT 101""",
            (body.longitude, body.latitude, body.dataset_id,
             body.longitude, body.latitude, body.radius_km * 1000),
        ).fetchall()
        items = []
        for well in wells[:100]:
            events = conn.execute(
                """SELECT e.id,e.event_type,e.start_md_m,e.end_md_m,
                          f.display_name AS formation_name
                   FROM drilling_event e
                   LEFT JOIN formation_interval fi ON fi.id=e.formation_interval_id
                   LEFT JOIN formation f ON f.id=fi.formation_id
                   WHERE e.wellbore_id=%s AND e.review_state='approved'
                     AND e.quality_issues='[]'::jsonb
                     AND EXISTS(SELECT 1 FROM event_passage ep WHERE ep.event_id=e.id)
                     AND (%s::uuid IS NULL OR fi.formation_id=%s)
                     AND (%s::numeric IS NULL OR e.end_md_m >= %s)
                     AND (%s::numeric IS NULL OR e.start_md_m <= %s)
                   ORDER BY e.start_md_m NULLS LAST,e.id LIMIT 101""",
                (well["wellbore_id"], body.formation_id, body.formation_id,
                 body.min_md_m, body.min_md_m, body.max_md_m, body.max_md_m),
            ).fetchall()
            items.append({**well, "events": events[:100],
                          "hazard_counts": dict(Counter(e["event_type"] for e in events[:100])),
                          "events_truncated": len(events) > 100})
    return {"location": {"latitude": body.latitude, "longitude": body.longitude},
            "radius_km": body.radius_km, "source_kind": dataset["kind"],
            "items": items, "truncated": len(wells) > 100,
            "score_kind": "historical_count_not_risk",
            "notice": "Location-only offset picture. No subsurface match, probability, or operating recommendation."}


@router.get("/knowledge/mitigation-links")
def mitigation_links(dataset_id: UUID, _principal=Depends(current_principal)):
    with connection() as conn:
        dataset = permitted_dataset(conn, dataset_id)
        rows = conn.execute(
            """SELECT e.id AS event_id,e.event_type,
                      COALESCE(f.display_name,'Formation unrecorded') AS formation_name,
                      COALESCE(NULLIF(e.mechanism,''),'mechanism unrecorded') AS mechanism,
                      m.id AS mitigation_id,m.action_taken,
                      COALESCE(m.effectiveness,'unknown') AS effectiveness
               FROM drilling_event e JOIN wellbore b ON b.id=e.wellbore_id
               JOIN well w ON w.id=b.well_id
               JOIN mitigation m ON m.event_id=e.id
               LEFT JOIN formation_interval fi ON fi.id=e.formation_interval_id
               LEFT JOIN formation f ON f.id=fi.formation_id
               WHERE w.dataset_id=%s AND e.review_state='approved'
                 AND e.quality_issues='[]'::jsonb
                 AND EXISTS(SELECT 1 FROM event_passage ep WHERE ep.event_id=e.id)
               ORDER BY e.event_type,formation_name,mechanism,m.action_taken,e.id LIMIT 501""",
            (dataset_id,),
        ).fetchall()
    groups: dict[tuple, dict] = {}
    for row in rows[:500]:
        key = (row["event_type"], row["formation_name"], row["mechanism"],
               row["action_taken"].strip())
        group = groups.setdefault(key, {
            "event_type": key[0], "formation_name": key[1], "mechanism": key[2],
            "action_taken": key[3], "effectiveness_counts": defaultdict(int),
            "event_ids": set(), "mitigation_ids": set(),
        })
        group["effectiveness_counts"][row["effectiveness"]] += 1
        group["event_ids"].add(str(row["event_id"]))
        group["mitigation_ids"].add(str(row["mitigation_id"]))
    items = [{**group, "effectiveness_counts": dict(group["effectiveness_counts"]),
              "event_ids": sorted(group["event_ids"]),
              "mitigation_ids": sorted(group["mitigation_ids"])}
             for group in groups.values()]
    return {"source_kind": dataset["kind"], "items": items,
            "truncated": len(rows) > 500,
            "notice": "Reported responses and outcomes, not causal evidence that an action cured an event."}


@router.get("/wellbores/{wellbore_id}/depth-track")
def depth_track(wellbore_id: UUID, _principal=Depends(current_principal)):
    with connection() as conn:
        identity = bore(conn, wellbore_id)
        intervals = [item for item in interval_rows(conn, wellbore_id)
                     if item["review_state"] == "approved" and item["datum_review"] == "approved"]
        eligible = may_approve_event({**identity, "kind": identity["data_kind"]})
        events = conn.execute(
            """SELECT e.id,e.event_type,e.start_md_m,e.end_md_m,e.severity
               FROM drilling_event e WHERE e.wellbore_id=%s AND e.review_state='approved'
                 AND e.quality_issues='[]'::jsonb
                 AND EXISTS(SELECT 1 FROM event_passage ep WHERE ep.event_id=e.id)
               ORDER BY e.start_md_m NULLS LAST,e.id LIMIT 201""",
            (wellbore_id,),
        ).fetchall() if eligible else []
        sources = conn.execute(
            "SELECT id FROM drilling_parameter_source WHERE dataset_id=%s AND qualification_state='qualified'",
            (identity["dataset_id"],),
        ).fetchall()
        samples = []
        for source in sources:
            samples.extend(row for row in eligible_anchors(conn, source["id"])
                           if row["wellbore_id"] == wellbore_id)
        samples.sort(key=lambda row: (row["md_m"], row["observed_at"]))
        samples = samples[:200]
    return {
        "wellbore_id": str(wellbore_id), "source_kind": identity["data_kind"],
        "intervals": [{"id": row["id"], "name": row["display_name"],
                       "top_md_m": row["top_md_m"], "base_md_m": row["base_md_m"],
                       "datum": row["datum"]} for row in intervals],
        "events": events[:200], "events_truncated": len(events) > 200,
        "parameters": [{"sample_id": row["sample_id"], "md_m": row["md_m"],
                        "rop_m_per_h": row["rop_m_per_h"],
                        "torque_kn_m": row["torque_kn_m"]} for row in samples],
        "parameter_note": "Qualified historical forward-drilling samples only; absence is not zero.",
        "missing_lanes": ["lithology", "reviewed_casing", "reviewed_mud_weight"]}
