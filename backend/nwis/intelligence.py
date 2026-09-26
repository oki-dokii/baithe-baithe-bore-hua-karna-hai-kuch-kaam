"""Read-only well intelligence. Heuristic mappings are not drilling predictions."""

import math
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

from nwis.db import connection
from nwis.ingestion.contracts import Hazard
from nwis.security import current_principal

router = APIRouter(prefix="/api/v1")
METHOD = "formation-relative-tvd-offset-v1"


def interpolate(points, value, inverse=False):
    x, y = ("tvd_m", "md_m") if inverse else ("md_m", "tvd_m")
    if len(points) < 2 or value is None:
        raise ValueError("survey_missing")
    pairs = [(float(p[x]), float(p[y])) for p in points]
    if any(not math.isfinite(v) for pair in pairs for v in pair):
        raise ValueError("invalid_survey")
    if any(b[0] <= a[0] for a, b in zip(pairs, pairs[1:])):
        raise ValueError("ambiguous_tvd_inverse" if inverse else "invalid_survey")
    if not pairs[0][0] <= value <= pairs[-1][0]:
        raise ValueError("survey_extrapolation_required")
    for (x0, y0), (x1, y1) in zip(pairs, pairs[1:]):
        if x0 <= value <= x1:
            return y0 + (value - x0) * (y1 - y0) / (x1 - x0)
    raise ValueError("survey_extrapolation_required")


def correlate(event, source, target, source_survey, target_survey):
    result = {
        "status": "unresolved",
        "reason": None,
        "mapped_start_md_m": None,
        "mapped_end_md_m": None,
        "method": METHOD,
        "quality": "unresolved",
    }
    try:
        if event["review_state"] != "approved":
            raise ValueError("event_not_approved")
        if event.get("quality_issues"):
            raise ValueError("event_quality_issues")
        if (
            not source
            or not target
            or source["review_state"] != "approved"
            or target["review_state"] != "approved"
        ):
            raise ValueError("interval_not_reviewed")
        if source["formation_id"] != target["formation_id"]:
            raise ValueError("formation_mismatch")
        if source["dataset_id"] != target["dataset_id"]:
            raise ValueError("dataset_mismatch")
        if event.get("source_depth_axis") not in (None, "MD"):
            raise ValueError("event_axis_not_md")
        if (
            event.get("source_datum")
            and event["source_datum"].strip().casefold()
            != (source.get("datum") or "").strip().casefold()
        ):
            raise ValueError("event_datum_mismatch")
        for interval in (source, target):
            if (
                interval.get("datum_review") != "approved"
                or interval.get("elevation_above_msl_m") is None
                or not interval.get("datum")
            ):
                raise ValueError("depth_reference_missing")
            if interval.get("base_md_m") is None or float(interval["base_md_m"]) <= float(
                interval["top_md_m"]
            ):
                raise ValueError("incomplete_formation_interval")
        start, end = event.get("start_md_m"), event.get("end_md_m")
        if (
            start is None
            or end is None
            or not float(source["top_md_m"])
            <= float(start)
            <= float(end)
            <= float(source["base_md_m"])
        ):
            raise ValueError("event_outside_source_interval")
        source_top = interpolate(source_survey, float(source["top_md_m"]))
        target_top = interpolate(target_survey, float(target["top_md_m"]))
        # Reject source folds too: offsets along a non-monotonic TVD interval are ambiguous.
        interpolate(source_survey, source_top, True)
        mapped = [
            interpolate(
                target_survey, target_top + interpolate(source_survey, float(v)) - source_top, True
            )
            for v in (start, end)
        ]
        # Inverse must be unique and the target interval must contain the entire mapping.
        if not float(target["top_md_m"]) <= mapped[0] <= mapped[1] <= float(target["base_md_m"]):
            raise ValueError("mapped_interval_outside_target")
        result.update(
            status="resolved",
            mapped_start_md_m=mapped[0],
            mapped_end_md_m=mapped[1],
            quality="reviewed_complete",
            warning="Heuristic formation-relative comparison; not a prediction or operating instruction",
        )
    except (ValueError, TypeError) as exc:
        result["reason"] = str(exc) if isinstance(exc, ValueError) else "invalid_depth_context"
    return result


def interval_rows(conn, wellbore_id):
    return conn.execute(
        """SELECT i.*,f.display_name,f.canonical_code,w.dataset_id,r.kind AS datum,
        r.elevation_above_msl_m,r.review_state AS datum_review
        FROM formation_interval i JOIN formation f ON f.id=i.formation_id
        JOIN wellbore b ON b.id=i.wellbore_id JOIN well w ON w.id=b.well_id
        JOIN depth_reference r ON r.id=i.depth_reference_id
        WHERE i.wellbore_id=%s ORDER BY i.top_md_m,i.version DESC""",
        (wellbore_id,),
    ).fetchall()


def survey(conn, wellbore_id):
    return conn.execute(
        """SELECT survey_version,md_m,tvd_m,inclination_deg,azimuth_deg FROM trajectory_station
        WHERE wellbore_id=%s AND survey_version=(SELECT max(survey_version) FROM trajectory_station WHERE wellbore_id=%s)
        ORDER BY md_m""",
        (wellbore_id, wellbore_id),
    ).fetchall()


def bore(conn, wellbore_id):
    row = conn.execute(
        """SELECT b.*,w.dataset_id,w.name,w.basin_name,d.kind AS data_kind,
        ST_X(w.surface_point::geometry) AS longitude,ST_Y(w.surface_point::geometry) AS latitude
        FROM wellbore b JOIN well w ON w.id=b.well_id JOIN dataset d ON d.id=w.dataset_id WHERE b.id=%s""",
        (wellbore_id,),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Wellbore not found")
    return row


@router.get("/intelligence/wellbores")
def wellbores(_principal=Depends(current_principal)):
    with connection() as conn:
        return {
            "items": conn.execute("""SELECT b.id,w.id AS well_id,w.name,b.external_id,w.dataset_id,
            d.kind AS data_kind,ST_X(w.surface_point::geometry) AS longitude,ST_Y(w.surface_point::geometry) AS latitude
            FROM wellbore b JOIN well w ON w.id=b.well_id JOIN dataset d ON d.id=w.dataset_id
            ORDER BY w.name,b.id LIMIT 100""").fetchall(),
            "limit": 100,
        }


@router.get("/wellbores/{wellbore_id}/trajectory")
def trajectory(wellbore_id: UUID, _principal=Depends(current_principal)):
    with connection() as conn:
        identity = bore(conn, wellbore_id)
        return {
            "wellbore": identity,
            "stations": survey(conn, wellbore_id),
            "intervals": interval_rows(conn, wellbore_id),
            "units": "m",
        }


@router.get("/wellbores/{wellbore_id}/analogues")
def analogues(
    wellbore_id: UUID,
    target_interval_id: UUID,
    radius_km: float = Query(5, ge=0.1, le=100),
    _principal=Depends(current_principal),
):
    with connection() as conn:
        active = bore(conn, wellbore_id)
        target = next(
            (i for i in interval_rows(conn, wellbore_id) if i["id"] == target_interval_id), None
        )
        if not target or target["review_state"] != "approved":
            raise HTTPException(422, "Select a reviewed interval belonging to the active wellbore")
        candidates = conn.execute(
            """SELECT b.id,w.name,w.id AS well_id,d.kind AS data_kind,
            ST_X(w.surface_point::geometry) AS longitude,ST_Y(w.surface_point::geometry) AS latitude,
            ST_Distance(w.surface_point,a.surface_point) AS surface_distance_m
            FROM well a JOIN well w ON w.dataset_id=a.dataset_id AND w.id<>a.id
            JOIN wellbore b ON b.well_id=w.id JOIN dataset d ON d.id=w.dataset_id
            WHERE a.id=%s AND ST_DWithin(w.surface_point,a.surface_point,%s)
            ORDER BY surface_distance_m,b.id LIMIT 101""",
            (active["well_id"], radius_km * 1000),
        ).fetchall()
        target_survey = survey(conn, wellbore_id)
        result = []
        for candidate in candidates[:100]:
            intervals = interval_rows(conn, candidate["id"])
            matching = [
                i
                for i in intervals
                if i["formation_id"] == target["formation_id"] and i["review_state"] == "approved"
            ]
            source = matching[0] if len(matching) == 1 else None
            thickness = None
            if source and source["base_md_m"] is not None and target["base_md_m"] is not None:
                lengths = [float(i["base_md_m"] - i["top_md_m"]) for i in (source, target)]
                thickness = min(lengths) / max(lengths)
            components = {
                "same_reviewed_formation": 1.0 if matching else 0.0,
                "md_thickness_similarity": thickness,
            }
            score = (
                (components["same_reviewed_formation"] * 0.75 + (thickness or 0) * 0.25)
                if thickness is not None
                else components["same_reviewed_formation"]
            )
            events = conn.execute(
                "SELECT * FROM drilling_event WHERE wellbore_id=%s AND review_state='approved' ORDER BY start_md_m NULLS LAST,id LIMIT 101",
                (candidate["id"],),
            ).fetchall()
            mapped = []
            candidate_survey = survey(conn, candidate["id"])
            for event in events[:100]:
                event_source = next(
                    (i for i in intervals if i["id"] == event["formation_interval_id"]), None
                )
                mapping = correlate(event, event_source, target, candidate_survey, target_survey)
                if len(matching) > 1:
                    mapping.update(
                        status="unresolved",
                        reason="ambiguous_formation_occurrence",
                        mapped_start_md_m=None,
                        mapped_end_md_m=None,
                        quality="unresolved",
                    )
                mapped.append(
                    {
                        "event_id": event["id"],
                        "event_type": event["event_type"],
                        "description": event["description"],
                        "source_start_md_m": event["start_md_m"],
                        "source_end_md_m": event["end_md_m"],
                        "source_interval_version": event_source["version"]
                        if event_source
                        else None,
                        "event_version": event["version"],
                        **mapping,
                    }
                )
            result.append(
                {
                    **candidate,
                    "components": components,
                    "similarity_score": score,
                    "score_kind": "heuristic_similarity_not_risk",
                    "missing_components": ["reservoir_properties", "lithology"]
                    + ([] if thickness is not None else ["md_thickness_similarity"]),
                    "source_interval": source,
                    "mappings": mapped,
                    "events_truncated": len(events) > 100,
                    "source_survey_version": candidate_survey[0]["survey_version"]
                    if candidate_survey
                    else None,
                }
            )
        result.sort(key=lambda r: (-r["similarity_score"], r["surface_distance_m"], str(r["id"])))
        return {
            "active": active,
            "target_interval": target,
            "radius_km": radius_km,
            "items": result,
            "truncated": len(candidates) > 100,
            "method": METHOD,
            "target_survey_version": target_survey[0]["survey_version"] if target_survey else None,
            "score_formula": "0.75 × shared formation + 0.25 × MD-thickness ratio; available weights renormalized. Distance is not in this score.",
        }


def event_case(conn, event_id):
    event = conn.execute(
        """SELECT e.*,w.name AS well_name,w.dataset_id,d.kind AS data_kind FROM drilling_event e
        JOIN wellbore b ON b.id=e.wellbore_id JOIN well w ON w.id=b.well_id JOIN dataset d ON d.id=w.dataset_id
        WHERE e.id=%s AND e.review_state='approved' """,
        (event_id,),
    ).fetchone()
    if not event:
        raise HTTPException(404, "Approved event not found")
    event["evidence"] = conn.execute(
        """SELECT p.id AS passage_id,p.document_id,p.page_number,p.text_version,
        d.filename,d.version AS document_version,p.ocr_applied,
        CASE WHEN %s::text IS NOT NULL THEN %s::text
             WHEN d.uploaded_by IS NULL AND d.access_class='demo' THEN p.raw_text ELSE NULL END AS quote
        FROM event_passage ep JOIN extracted_passage p ON p.id=ep.passage_id
        JOIN source_document d ON d.id=p.document_id WHERE ep.event_id=%s ORDER BY p.page_number""",
        (event["source_fields"].get("quote"), event["source_fields"].get("quote"), event_id),
    ).fetchall()
    for table in ("mitigation", "event_outcome", "npt_event"):
        # The identifier is chosen only from this fixed server-side tuple, never user input.
        event[table] = conn.execute(
            f"SELECT * FROM {table} WHERE event_id=%s ORDER BY id", (event_id,)
        ).fetchall()
    return event


@router.get("/events/{event_id}")
def case_file(event_id: UUID, _principal=Depends(current_principal)):
    with connection() as conn:
        return event_case(conn, event_id)


@router.get("/events/{event_id}/evidence/{passage_id}")
def evidence(event_id: UUID, passage_id: UUID, principal=Depends(current_principal)):
    with connection() as conn:
        event = event_case(conn, event_id)
        item = next((p for p in event["evidence"] if p["passage_id"] == passage_id), None)
        if not item:
            raise HTTPException(404, "Supporting passage not found")
        item["representation"] = "approved_quote"
        if principal.role in ("reviewer", "admin"):
            item["raw_text"] = conn.execute(
                "SELECT raw_text FROM extracted_passage WHERE id=%s", (passage_id,)
            ).fetchone()["raw_text"]
            item["representation"] = "reviewer_source_page"
        return item


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    dataset_id: UUID
    question: str = Field(default="", max_length=1000)
    wellbore_id: UUID | None = None
    formation_id: UUID | None = None
    hazard: Hazard | None = None
    min_md_m: float | None = Field(default=None, ge=0)
    max_md_m: float | None = Field(default=None, ge=0)
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=100000)

    @model_validator(mode="after")
    def depth_order(self):
        if (
            self.min_md_m is not None
            and self.max_md_m is not None
            and self.max_md_m < self.min_md_m
        ):
            raise ValueError("Depth interval is reversed")
        return self


@router.post("/query")
def search(body: SearchRequest, _principal=Depends(current_principal)):
    with connection() as conn:
        if not conn.execute("SELECT 1 FROM dataset WHERE id=%s", (body.dataset_id,)).fetchone():
            raise HTTPException(404, "Dataset not found")
        if body.wellbore_id and bore(conn, body.wellbore_id)["dataset_id"] != body.dataset_id:
            raise HTTPException(422, "Wellbore does not belong to the selected dataset")
        # Search approved claims, not whole source pages containing unreviewed material.
        rows = conn.execute(
            """SELECT e.id,e.event_type,e.description,e.start_md_m,e.end_md_m,w.name AS well_name,
            e.wellbore_id, e.quality_issues,
            ts_rank_cd(to_tsvector('english',coalesce(e.description,'') || ' ' || coalesce(e.source_fields->>'quote','')),
                websearch_to_tsquery('english',%s)) AS retrieval_score
            FROM drilling_event e JOIN wellbore b ON b.id=e.wellbore_id JOIN well w ON w.id=b.well_id
            LEFT JOIN formation_interval i ON i.id=e.formation_interval_id
            WHERE w.dataset_id=%s AND e.review_state='approved'
            AND EXISTS(SELECT 1 FROM event_passage ep WHERE ep.event_id=e.id)
            AND (%s::uuid IS NULL OR b.id=%s) AND (%s::uuid IS NULL OR i.formation_id=%s)
            AND (%s::text IS NULL OR e.event_type=%s)
            AND (%s::float IS NULL OR e.end_md_m>=%s) AND (%s::float IS NULL OR e.start_md_m<=%s)
            AND (%s='' OR to_tsvector('english',coalesce(e.description,'') || ' ' || coalesce(e.source_fields->>'quote','')) @@ websearch_to_tsquery('english',%s))
            ORDER BY retrieval_score DESC,e.id LIMIT %s OFFSET %s""",
            (
                body.question,
                body.dataset_id,
                body.wellbore_id,
                body.wellbore_id,
                body.formation_id,
                body.formation_id,
                body.hazard,
                body.hazard,
                body.min_md_m,
                body.min_md_m,
                body.max_md_m,
                body.max_md_m,
                body.question.strip(),
                body.question,
                body.limit + 1,
                body.offset,
            ),
        ).fetchall()
        items = []
        for row in rows[: body.limit]:
            citations = event_case(conn, row["id"])["evidence"]
            supported = [c for c in citations if c["quote"]]
            if supported:
                items.append({**row, "citations": supported})
        return {
            "items": items,
            "next_offset": body.offset + body.limit if len(rows) > body.limit else None,
            "retrieval_mode": "postgresql_full_text",
            "semantic_model": None,
            "answer_kind": "extractive_evidence_list",
            "abstention_reason": None if items else "no_approved_supporting_evidence",
            "notice": "Source-backed historical claims only. No generated advice or semantic embedding model.",
        }
