"""Read-only planning and evidence views; no risk probability or drilling advice."""

from collections import Counter, defaultdict
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from nwis.db import connection
from nwis.drilling_parameters import eligible_anchors
from nwis.intelligence import bore, interval_rows
from nwis.provenance import may_approve_event
from nwis.security import current_principal, require_role

router = APIRouter(prefix="/api/v1")


class CasingProgramInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hole_diameter_m: float = Field(gt=0)
    casing_diameter_m: float = Field(gt=0)
    setting_depth_md_m: float = Field(ge=0)
    casing_type: str = Field(min_length=1)
    cement_volume_m3: float | None = Field(default=None, ge=0)
    cement_type: str | None = None
    recorded_outcome: str | None = None
    notes: str | None = None


class MudProgramInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    interval_top_md_m: float = Field(ge=0)
    interval_base_md_m: float = Field(ge=0)
    mud_type: str = Field(min_length=1)
    mud_density_kg_m3: float = Field(gt=0)
    rheology_notes: str | None = None

    @model_validator(mode="after")
    def valid_interval(self):
        if self.interval_base_md_m < self.interval_top_md_m:
            raise ValueError("interval_base_md_m must be >= interval_top_md_m")
        return self


class ReservoirPropertyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    formation_interval_id: UUID
    property_type: str = Field(min_length=1, max_length=50)
    value: float | None = None
    unit: str = Field(min_length=1, max_length=20)
    top_md_m: float | None = Field(default=None, ge=0)
    base_md_m: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def valid_interval(self):
        if self.top_md_m is not None and self.base_md_m is not None and self.base_md_m < self.top_md_m:
            raise ValueError("base_md_m must be >= top_md_m")
        return self


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

        # Casing Program (Data Source viii)
        casing_rows = conn.execute(
            """SELECT c.id, c.hole_diameter_m, c.casing_diameter_m, c.setting_depth_md_m, c.casing_type,
                      m.cement_volume_m3, m.cement_type, m.recorded_outcome
               FROM casing_program c
               LEFT JOIN cementing_operation m ON m.casing_id = c.id
               WHERE c.wellbore_id = %s
               ORDER BY c.setting_depth_md_m ASC""",
            (wellbore_id,),
        ).fetchall()

        # Mud Program (Data Source viii)
        mud_rows = conn.execute(
            """SELECT id, interval_top_md_m, interval_base_md_m, mud_type, mud_density_kg_m3, rheology_notes
               FROM mud_program
               WHERE wellbore_id = %s
               ORDER BY interval_top_md_m ASC""",
            (wellbore_id,),
        ).fetchall()

        # Reservoir Properties (Data Source v)
        reservoir_rows = conn.execute(
            """SELECT rp.id, rp.formation_interval_id, rp.property_type, rp.value, rp.unit,
                      rp.top_md_m, rp.base_md_m, f.display_name AS formation_name
               FROM reservoir_property rp
               JOIN formation_interval fi ON fi.id = rp.formation_interval_id
               JOIN formation f ON f.id = fi.formation_id
               WHERE fi.wellbore_id = %s
               ORDER BY rp.top_md_m ASC NULLS LAST, rp.property_type ASC""",
            (wellbore_id,),
        ).fetchall()

        missing = ["lithology"]
        if not casing_rows:
            missing.append("reviewed_casing")
        if not mud_rows:
            missing.append("reviewed_mud_weight")

    return {
        "wellbore_id": str(wellbore_id), "source_kind": identity["data_kind"],
        "intervals": [{"id": row["id"], "name": row["display_name"],
                       "top_md_m": row["top_md_m"], "base_md_m": row["base_md_m"],
                       "datum": row["datum"]} for row in intervals],
        "events": events[:200], "events_truncated": len(events) > 200,
        "parameters": [{"sample_id": row["sample_id"], "md_m": row["md_m"],
                        "rop_m_per_h": row["rop_m_per_h"],
                        "torque_kn_m": row["torque_kn_m"]} for row in samples],
        "casing_program": [
            {
                "id": str(r["id"]),
                "casing_type": r["casing_type"],
                "setting_depth_md_m": float(r["setting_depth_md_m"]) if r["setting_depth_md_m"] is not None else None,
                "hole_diameter_m": float(r["hole_diameter_m"]) if r["hole_diameter_m"] is not None else None,
                "casing_diameter_m": float(r["casing_diameter_m"]) if r["casing_diameter_m"] is not None else None,
                "cement_type": r["cement_type"],
                "cement_volume_m3": float(r["cement_volume_m3"]) if r["cement_volume_m3"] is not None else None,
                "recorded_outcome": r["recorded_outcome"],
            }
            for r in casing_rows
        ],
        "mud_program": [
            {
                "id": str(r["id"]),
                "top_md_m": float(r["interval_top_md_m"]) if r["interval_top_md_m"] is not None else None,
                "base_md_m": float(r["interval_base_md_m"]) if r["interval_base_md_m"] is not None else None,
                "mud_type": r["mud_type"],
                "mud_density_kg_m3": float(r["mud_density_kg_m3"]) if r["mud_density_kg_m3"] is not None else None,
                "rheology_notes": r["rheology_notes"],
            }
            for r in mud_rows
        ],
        "reservoir_properties": [
            {
                "id": str(r["id"]),
                "formation_interval_id": str(r["formation_interval_id"]),
                "formation_name": r["formation_name"],
                "property_type": r["property_type"],
                "value": float(r["value"]) if r["value"] is not None else None,
                "unit": r["unit"],
                "top_md_m": float(r["top_md_m"]) if r["top_md_m"] is not None else None,
                "base_md_m": float(r["base_md_m"]) if r["base_md_m"] is not None else None,
            }
            for r in reservoir_rows
        ],
        "parameter_note": "Qualified historical forward-drilling samples only; absence is not zero.",
        "missing_lanes": missing,
    }


@router.get("/wellbores/{wellbore_id}/casing-program")
def get_casing_program(wellbore_id: UUID, _principal=Depends(current_principal)):
    """Retrieve casing program and cementing records for a wellbore (Data Source viii)."""
    with connection() as conn:
        rows = conn.execute(
            """SELECT c.id, c.hole_diameter_m, c.casing_diameter_m, c.setting_depth_md_m, c.casing_type,
                      m.cement_volume_m3, m.cement_type, m.recorded_outcome, m.notes AS cementing_notes
               FROM casing_program c
               LEFT JOIN cementing_operation m ON m.casing_id = c.id
               WHERE c.wellbore_id = %s
               ORDER BY c.setting_depth_md_m ASC""",
            (wellbore_id,),
        ).fetchall()
        return {
            "wellbore_id": str(wellbore_id),
            "casing_strings": [
                {
                    "id": str(r["id"]),
                    "hole_diameter_m": float(r["hole_diameter_m"]) if r["hole_diameter_m"] is not None else None,
                    "casing_diameter_m": float(r["casing_diameter_m"]) if r["casing_diameter_m"] is not None else None,
                    "setting_depth_md_m": float(r["setting_depth_md_m"]) if r["setting_depth_md_m"] is not None else None,
                    "casing_type": r["casing_type"],
                    "cementing": {
                        "cement_volume_m3": float(r["cement_volume_m3"]) if r["cement_volume_m3"] is not None else None,
                        "cement_type": r["cement_type"],
                        "recorded_outcome": r["recorded_outcome"],
                        "notes": r["cementing_notes"],
                    } if r["cement_type"] or r["cement_volume_m3"] is not None else None,
                }
                for r in rows
            ],
        }


@router.post("/wellbores/{wellbore_id}/casing-program", status_code=201)
def add_casing_program(
    wellbore_id: UUID,
    body: CasingProgramInput,
    principal=Depends(require_role("engineer")),
):
    """Record a casing shoe and optional cementing operation for a wellbore."""
    with connection() as conn:
        wellbore = conn.execute("SELECT id FROM wellbore WHERE id=%s", (wellbore_id,)).fetchone()
        if not wellbore:
            raise HTTPException(404, "Wellbore not found")
        casing_id = uuid4()
        conn.execute(
            """INSERT INTO casing_program(id, wellbore_id, hole_diameter_m, casing_diameter_m, setting_depth_md_m, casing_type)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (casing_id, wellbore_id, body.hole_diameter_m, body.casing_diameter_m, body.setting_depth_md_m, body.casing_type),
        )
        if body.cement_type or body.cement_volume_m3 is not None:
            conn.execute(
                """INSERT INTO cementing_operation(id, casing_id, cement_volume_m3, cement_type, recorded_outcome, notes)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (uuid4(), casing_id, body.cement_volume_m3, body.cement_type, body.recorded_outcome, body.notes),
            )
        conn.execute(
            "INSERT INTO audit_log(actor_name, action, entity_type, entity_id) VALUES (%s, 'add_casing_program', 'wellbore', %s)",
            (principal.name, wellbore_id),
        )
        return {"id": str(casing_id), "status": "casing_recorded", "wellbore_id": str(wellbore_id)}


@router.get("/wellbores/{wellbore_id}/mud-program")
def get_mud_program(wellbore_id: UUID, _principal=Depends(current_principal)):
    """Retrieve planned and recorded mud program intervals for a wellbore (Data Source viii)."""
    with connection() as conn:
        rows = conn.execute(
            """SELECT id, interval_top_md_m, interval_base_md_m, mud_type, mud_density_kg_m3, rheology_notes
               FROM mud_program
               WHERE wellbore_id = %s
               ORDER BY interval_top_md_m ASC""",
            (wellbore_id,),
        ).fetchall()
        return {
            "wellbore_id": str(wellbore_id),
            "mud_intervals": [
                {
                    "id": str(r["id"]),
                    "interval_top_md_m": float(r["interval_top_md_m"]) if r["interval_top_md_m"] is not None else None,
                    "interval_base_md_m": float(r["interval_base_md_m"]) if r["interval_base_md_m"] is not None else None,
                    "mud_type": r["mud_type"],
                    "mud_density_kg_m3": float(r["mud_density_kg_m3"]) if r["mud_density_kg_m3"] is not None else None,
                    "mud_density_ppg": round(float(r["mud_density_kg_m3"]) / 119.826, 2) if r["mud_density_kg_m3"] is not None else None,
                    "rheology_notes": r["rheology_notes"],
                }
                for r in rows
            ],
        }


@router.post("/wellbores/{wellbore_id}/mud-program", status_code=201)
def add_mud_program(
    wellbore_id: UUID,
    body: MudProgramInput,
    principal=Depends(require_role("engineer")),
):
    """Record a mud program interval for a wellbore."""
    with connection() as conn:
        wellbore = conn.execute("SELECT id FROM wellbore WHERE id=%s", (wellbore_id,)).fetchone()
        if not wellbore:
            raise HTTPException(404, "Wellbore not found")
        mud_id = uuid4()
        conn.execute(
            """INSERT INTO mud_program(id, wellbore_id, interval_top_md_m, interval_base_md_m, mud_type, mud_density_kg_m3, rheology_notes)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (mud_id, wellbore_id, body.interval_top_md_m, body.interval_base_md_m, body.mud_type, body.mud_density_kg_m3, body.rheology_notes),
        )
        conn.execute(
            "INSERT INTO audit_log(actor_name, action, entity_type, entity_id) VALUES (%s, 'add_mud_program', 'wellbore', %s)",
            (principal.name, wellbore_id),
        )
        return {"id": str(mud_id), "status": "mud_interval_recorded", "wellbore_id": str(wellbore_id)}


@router.get("/wellbores/{wellbore_id}/reservoir-properties")
def get_reservoir_properties(wellbore_id: UUID, _principal=Depends(current_principal)):
    """Retrieve reservoir properties (porosity, permeability, pore pressure, etc.) for a wellbore (Data Source v)."""
    with connection() as conn:
        rows = conn.execute(
            """SELECT rp.id, rp.formation_interval_id, rp.property_type, rp.value, rp.unit,
                      rp.top_md_m, rp.base_md_m, f.display_name AS formation_name
               FROM reservoir_property rp
               JOIN formation_interval fi ON fi.id = rp.formation_interval_id
               JOIN formation f ON f.id = fi.formation_id
               WHERE fi.wellbore_id = %s
               ORDER BY rp.top_md_m ASC NULLS LAST, rp.property_type ASC""",
            (wellbore_id,),
        ).fetchall()
        return {
            "wellbore_id": str(wellbore_id),
            "reservoir_properties": [
                {
                    "id": str(r["id"]),
                    "formation_interval_id": str(r["formation_interval_id"]),
                    "formation_name": r["formation_name"],
                    "property_type": r["property_type"],
                    "value": float(r["value"]) if r["value"] is not None else None,
                    "unit": r["unit"],
                    "top_md_m": float(r["top_md_m"]) if r["top_md_m"] is not None else None,
                    "base_md_m": float(r["base_md_m"]) if r["base_md_m"] is not None else None,
                }
                for r in rows
            ],
        }


@router.post("/wellbores/{wellbore_id}/reservoir-properties", status_code=201)
def add_reservoir_property(
    wellbore_id: UUID,
    body: ReservoirPropertyInput,
    principal=Depends(require_role("engineer")),
):
    """Record a verified reservoir property for a formation interval in a wellbore (Data Source v)."""
    with connection() as conn:
        interval = conn.execute(
            "SELECT id FROM formation_interval WHERE id=%s AND wellbore_id=%s",
            (body.formation_interval_id, wellbore_id),
        ).fetchone()
        if not interval:
            raise HTTPException(404, "Formation interval not found for this wellbore")
        prop_id = uuid4()
        conn.execute(
            """INSERT INTO reservoir_property(id, formation_interval_id, property_type, value, unit, top_md_m, base_md_m)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (prop_id, body.formation_interval_id, body.property_type, body.value, body.unit, body.top_md_m, body.base_md_m),
        )
        conn.execute(
            "INSERT INTO audit_log(actor_name, action, entity_type, entity_id) VALUES (%s, 'add_reservoir_property', 'wellbore', %s)",
            (principal.name, wellbore_id),
        )
        return {"id": str(prop_id), "status": "reservoir_property_recorded", "wellbore_id": str(wellbore_id)}
