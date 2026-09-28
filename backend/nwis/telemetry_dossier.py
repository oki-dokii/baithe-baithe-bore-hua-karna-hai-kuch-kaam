"""Read-only evidence for historical telemetry source screening."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from nwis.db import connection
from nwis.drilling_parameters import HistoricalSample
from nwis.security import current_principal
from nwis.telemetry_screen import screen_batch

router = APIRouter(prefix="/api/v1")


@router.get("/telemetry-sources")
def telemetry_sources(_principal=Depends(current_principal)):
    with connection() as conn:
        items = conn.execute(
            """SELECT s.id,s.external_id,s.source_kind,s.qualification_state,
                      s.created_at,s.dataset_id,d.name AS dataset_name,d.kind AS data_kind,
                      d.authorization_state,d.applicability,
                      (SELECT count(*) FROM drilling_parameter_sample p WHERE p.source_id=s.id) AS stored_revisions
               FROM drilling_parameter_source s JOIN dataset d ON d.id=s.dataset_id
               ORDER BY s.created_at DESC,s.id LIMIT 101"""
        ).fetchall()
        return {"items": items[:100], "truncated": len(items) > 100}


@router.get("/telemetry-sources/{source_id}/quality-dossier")
def quality_dossier(source_id: UUID, _principal=Depends(current_principal)):
    with connection() as conn:
        source = conn.execute(
            """SELECT s.id,s.external_id,s.source_sha256,s.source_kind,
                      s.source_timezone,s.md_datum,s.source_units,s.mapping_version,
                      s.units_reviewed,s.timezone_reviewed,s.datum_reviewed,
                      s.rig_state_reviewed,s.qualification_state,s.qualified_at,
                      s.created_at,s.dataset_id,d.name AS dataset_name,d.kind AS data_kind,
                      d.origin_kind,d.authorization_state,d.applicability,d.qualification_status AS dataset_qualification_state
               FROM drilling_parameter_source s JOIN dataset d ON d.id=s.dataset_id
               WHERE s.id=%s""",
            (source_id,),
        ).fetchone()
        if source is None:
            raise HTTPException(404, "Historical telemetry source not found")
        counts = conn.execute(
            """SELECT count(*) AS stored_revisions,count(DISTINCT source_record_id) AS distinct_records
               FROM drilling_parameter_sample WHERE source_id=%s""", (source_id,)
        ).fetchone()
        # Bound the synchronous screen: an incomplete dossier must not imply a pass.
        if counts["stored_revisions"] > 100000:
            return {"source": source, "record_counts": counts, "screen": None,
                    "dossier_state": "too_large_for_live_screen",
                    "notice": "No live quality decision; export requires a bounded offline screen. Source qualification is separate from ML authorization."}
        rows = conn.execute(
            """SELECT DISTINCT ON (source_record_id)
                      wellbore_id,source_record_id,revision,operation,observed_at,
                      available_at,received_at,md_m,tvd_m,depth_reference_id,
                      rig_state,quality,source_quality_code,rop_m_per_h,wob_kn,rpm,
                      torque_kn_m,flow_in_l_per_min,mud_density_kg_per_m3
               FROM drilling_parameter_sample WHERE source_id=%s
               ORDER BY source_record_id,revision DESC""", (source_id,)
        ).fetchall()
        screen = screen_batch(HistoricalSample.model_validate({**row, "raw_values": {}}) for row in rows)
        return {"source": source, "record_counts": counts, "screen": screen,
                "dossier_state": "screened",
                "notice": "Screening is reproducible from current revisions. A screen pass is not engineering qualification, verified event coverage, or authorization to train/deploy ML."}
