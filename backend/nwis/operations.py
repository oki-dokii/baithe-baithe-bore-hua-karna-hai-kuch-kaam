"""Deterministic synthetic replay. Historical lookahead is not a risk probability."""

import math
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from nwis.db import connection
from nwis.ingestion.api import receipt, save_receipt
from nwis.intelligence import analogues, event_case
from nwis.security import current_principal, require_role
from nwis.seed import stable_id

router = APIRouter(prefix="/api/v1")
SCENARIO = "golden-mud-loss-v1"
DEPTHS = (2029.0, 2030.0, 2030.0, 2031.0, 2141.0)
LOOKAHEAD = 100.0
STALE_SECONDS = 15
RULE = "historical-lookahead-v1"
TARGET = stable_id("interval", "A-F1")
ACTIVE = stable_id("wellbore", "SYN-A-MAIN")


class CreateReplay(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    scenario_id: Literal["golden-mud-loss-v1"] = SCENARIO
    speed: float = Field(default=1, ge=0.1, le=10)


class Control(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["resume", "pause", "step", "reset"]
    expected_version: int = Field(ge=1)


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["acknowledge", "review", "resolve", "dismiss", "reopen"]
    expected_version: int = Field(ge=1)
    rationale: str = Field(min_length=3, max_length=2000)


class Feedback(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action_taken: str = Field(min_length=3, max_length=2000)
    observed_outcome: Literal["unknown", "incident_observed", "no_incident_observed"]
    rationale: str = Field(min_length=3, max_length=2000)


def should_alert(md, start, end):
    return md <= end and md + LOOKAHEAD >= start


def episode(session_id, hazard, mapped_start):
    return f"{session_id}:{TARGET}:{hazard}:{math.floor(mapped_start / 50)}"


def new_session(conn, actor, speed, parent=None):
    if not conn.execute("SELECT 1 FROM wellbore WHERE id=%s", (ACTIVE,)).fetchone():
        raise HTTPException(409, "Load the owned golden fixture before starting replay")
    session_id = uuid4()
    conn.execute(
        """INSERT INTO replay_session(id,active_wellbore_id,scenario_id,state,speed,created_by,parent_session_id)
        VALUES(%s,%s,%s,'paused',%s,%s,%s)""",
        (session_id, ACTIVE, SCENARIO, speed, actor, parent),
    )
    conn.execute(
        "INSERT INTO audit_log(actor_name,action,entity_type,entity_id) VALUES(%s,'create_replay','replay_session',%s)",
        (actor, session_id),
    )
    return {"id": str(session_id), "revision": 1, "state": "paused", "source_mode": "SIMULATED"}


@router.post("/replay-sessions", status_code=201)
def create_replay(
    body: CreateReplay,
    idempotency_key: str = Header(...),
    principal=Depends(require_role("engineer")),
):
    with connection() as conn:
        digest, old = receipt(
            conn, principal.name, idempotency_key, ["create_replay", body.model_dump()]
        )
        if old:
            return old
        return save_receipt(
            conn,
            principal.name,
            idempotency_key,
            digest,
            new_session(conn, principal.name, body.speed),
        )


def evidence_changed(conn, alert_id):
    return conn.execute(
        """SELECT EXISTS(
            SELECT 1 FROM alert_evidence ae JOIN drilling_event e ON e.id=ae.event_id
            JOIN interval_mapping im ON im.id=ae.interval_mapping_id
            JOIN formation_interval t ON t.id=im.target_interval_id
            LEFT JOIN formation_interval s ON s.id=e.formation_interval_id
            LEFT JOIN depth_reference sr ON sr.id=s.depth_reference_id
            LEFT JOIN depth_reference tr ON tr.id=t.depth_reference_id
            WHERE ae.alert_id=%s AND (e.review_state<>'approved' OR e.version<>ae.event_version
                OR e.quality_issues<>'[]'::jsonb OR t.review_state<>'approved' OR t.version<>im.target_interval_version
                OR s.review_state IS DISTINCT FROM 'approved'
                OR sr.review_state IS DISTINCT FROM 'approved' OR tr.review_state IS DISTINCT FROM 'approved'
                OR sr.elevation_above_msl_m IS NULL OR tr.elevation_above_msl_m IS NULL
                OR s.version::text IS DISTINCT FROM ae.evidence_snapshot->>'source_interval_version'
                OR (SELECT max(survey_version)::text FROM trajectory_station WHERE wellbore_id=e.wellbore_id)
                    IS DISTINCT FROM ae.evidence_snapshot->>'source_survey_version'
                OR (SELECT max(survey_version)::text FROM trajectory_station WHERE wellbore_id=t.wellbore_id)
                    IS DISTINCT FROM ae.evidence_snapshot->>'target_survey_version'
                OR NOT EXISTS(SELECT 1 FROM event_passage ep WHERE ep.event_id=e.id AND ep.passage_id=ae.passage_id))) AS changed
        """,
        (alert_id,),
    ).fetchone()["changed"]


def update_evidence_health(conn, session_id):
    for row in conn.execute(
        "SELECT id,relevance FROM alert WHERE replay_session_id=%s FOR UPDATE", (session_id,)
    ).fetchall():
        if row["relevance"] != "review_required" and evidence_changed(conn, row["id"]):
            conn.execute(
                "UPDATE alert SET relevance='review_required',revision=revision+1 WHERE id=%s",
                (row["id"],),
            )


def advance(conn, session):
    sequence = session["next_sequence"]
    if sequence >= len(DEPTHS):
        raise HTTPException(409, "Replay is complete; reset creates a new session")
    md = DEPTHS[sequence]
    now = datetime.now(timezone.utc)
    conn.execute(
        """INSERT INTO telemetry_sample(id,wellbore_id,replay_session_id,sequence,observed_at,received_at,md_m,tvd_m,quality)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'synthetic_fixture')""",
        (uuid4(), ACTIVE, session["id"], sequence, now, now, md, md),
    )
    # Each accepted replay step is a newly received sample. GETs never re-evaluate or create alerts.
    comparison = analogues(ACTIVE, TARGET, 5, None)
    if (datetime.now(timezone.utc) - now).total_seconds() > STALE_SECONDS:
        raise HTTPException(
            503, "Evaluation exceeded the sample freshness window; nothing was committed"
        )
    eligible = {}
    for candidate in comparison["items"]:
        for mapping in candidate["mappings"]:
            if mapping["status"] != "resolved":
                continue
            event = conn.execute(
                "SELECT * FROM drilling_event WHERE id=%s FOR SHARE", (mapping["event_id"],)
            ).fetchone()
            if (
                event["review_state"] != "approved"
                or event["version"] != mapping["event_version"]
                or event["quality_issues"]
            ):
                continue
            case = event_case(conn, event["id"])
            citations = [c for c in case["evidence"] if c["quote"]]
            if not citations:
                continue
            key = episode(session["id"], event["event_type"], mapping["mapped_start_md_m"])
            eligible.setdefault(key, []).append((event, mapping, citations, candidate))
    update_evidence_health(conn, session["id"])
    for key, support in eligible.items():
        in_window = any(
            should_alert(md, m["mapped_start_md_m"], m["mapped_end_md_m"]) for _, m, _, _ in support
        )
        existing = conn.execute(
            "SELECT * FROM alert WHERE episode_key=%s FOR UPDATE", (key,)
        ).fetchone()
        if not in_window and not existing:
            continue
        start = min(m["mapped_start_md_m"] for _, m, _, _ in support)
        end = max(m["mapped_end_md_m"] for _, m, _, _ in support)
        relevance = "passed" if md > end else "at_interval" if md >= start else "upcoming"
        if existing:
            alert_id = existing["id"]
            conn.execute(
                """UPDATE alert SET current_md_m=%s,last_seen_at=%s,seen_count=seen_count+%s,
                relevance=CASE WHEN relevance='review_required' THEN relevance ELSE %s END,revision=revision+1 WHERE id=%s""",
                (md, now, int(in_window), relevance, alert_id),
            )
        else:
            alert_id = uuid4()
            conn.execute(
                """INSERT INTO alert(id,active_wellbore_id,replay_session_id,target_interval_id,hazard_type,
                depth_band,episode_key,current_md_m,rule_version,config_version,relevance)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,'golden-v1',%s)""",
                (
                    alert_id,
                    ACTIVE,
                    session["id"],
                    TARGET,
                    support[0][0]["event_type"],
                    math.floor(start / 50),
                    key,
                    md,
                    RULE,
                    relevance,
                ),
            )
        for event, mapping, citations, candidate in support:
            for citation in citations:
                if conn.execute(
                    "SELECT 1 FROM alert_evidence WHERE alert_id=%s AND event_id=%s AND passage_id=%s",
                    (alert_id, event["id"], citation["passage_id"]),
                ).fetchone():
                    continue
                mapping_id = uuid4()
                conn.execute(
                    """INSERT INTO interval_mapping(id,source_event_id,target_interval_id,source_event_version,
                    target_interval_version,mapped_start_md_m,mapped_end_md_m,method,method_version,status)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'1','resolved')""",
                    (
                        mapping_id,
                        event["id"],
                        TARGET,
                        event["version"],
                        comparison["target_interval"]["version"],
                        mapping["mapped_start_md_m"],
                        mapping["mapped_end_md_m"],
                        mapping["method"],
                    ),
                )
                snapshot = {
                    "quote": citation["quote"],
                    "filename": citation["filename"],
                    "page_number": citation["page_number"],
                    "document_version": citation["document_version"],
                    "text_version": citation["text_version"],
                    "source_interval_version": mapping["source_interval_version"],
                    "source_survey_version": candidate["source_survey_version"],
                    "target_survey_version": comparison["target_survey_version"],
                    "source_well": candidate["name"],
                    "source_start_md_m": float(mapping["source_start_md_m"]),
                    "source_end_md_m": float(mapping["source_end_md_m"]),
                    "mapped_start_md_m": mapping["mapped_start_md_m"],
                    "mapped_end_md_m": mapping["mapped_end_md_m"],
                    "surface_distance_m": candidate["surface_distance_m"],
                    "data_kind": candidate["data_kind"],
                }
                conn.execute(
                    """INSERT INTO alert_evidence(alert_id,event_id,interval_mapping_id,passage_id,event_version,evidence_snapshot)
                    VALUES(%s,%s,%s,%s,%s,%s)""",
                    (
                        alert_id,
                        event["id"],
                        mapping_id,
                        citation["passage_id"],
                        event["version"],
                        Jsonb(snapshot),
                    ),
                )
    state = "completed" if sequence + 1 == len(DEPTHS) else session["state"]
    conn.execute(
        """UPDATE replay_session SET next_sequence=next_sequence+1,revision=revision+1,state=%s,
        next_tick_at=now()+(2/speed)*interval '1 second' WHERE id=%s""",
        (state, session["id"]),
    )
    return {
        "id": str(session["id"]),
        "sequence": sequence,
        "md_m": md,
        "state": state,
        "revision": session["revision"] + 1,
    }


@router.post("/replay-sessions/{session_id}/control")
def control(
    session_id: UUID,
    body: Control,
    idempotency_key: str = Header(...),
    principal=Depends(require_role("engineer")),
):
    with connection() as conn:
        digest, old = receipt(
            conn, principal.name, idempotency_key, ["control", session_id, body.model_dump()]
        )
        if old:
            return old
        session = conn.execute(
            "SELECT * FROM replay_session WHERE id=%s FOR UPDATE", (session_id,)
        ).fetchone()
        if not session:
            raise HTTPException(404, "Replay not found")
        if session["revision"] != body.expected_version:
            raise HTTPException(409, "Replay changed; refresh before controlling it")
        if body.action == "reset":
            conn.execute(
                "UPDATE replay_session SET state='stopped',revision=revision+1 WHERE id=%s",
                (session_id,),
            )
            result = new_session(conn, principal.name, session["speed"], session_id)
        elif body.action == "step":
            if session["state"] != "paused":
                raise HTTPException(409, "Pause the replay before stepping")
            result = advance(conn, session)
        else:
            if session["state"] in ("completed", "stopped"):
                raise HTTPException(409, "Reset this replay to continue")
            state = "running" if body.action == "resume" else "paused"
            conn.execute(
                "UPDATE replay_session SET state=%s,revision=revision+1,next_tick_at=now() WHERE id=%s",
                (state, session_id),
            )
            result = {"id": str(session_id), "revision": session["revision"] + 1, "state": state}
        conn.execute(
            "INSERT INTO audit_log(actor_name,action,entity_type,entity_id) VALUES(%s,%s,'replay_session',%s)",
            (principal.name, body.action, session_id),
        )
        return save_receipt(conn, principal.name, idempotency_key, digest, result)


def replay_tick():
    with connection() as conn:
        conn.execute(
            """INSERT INTO service_heartbeat(service) VALUES('replay') ON CONFLICT(service) DO UPDATE SET last_seen_at=now()"""
        )
        session = conn.execute(
            "SELECT * FROM replay_session WHERE state='running' AND next_tick_at<=now() ORDER BY next_tick_at FOR UPDATE SKIP LOCKED LIMIT 1"
        ).fetchone()
        if not session:
            return False
        advance(conn, session)
        return True


@router.get("/replay-sessions")
def sessions(_principal=Depends(current_principal)):
    with connection() as conn:
        return conn.execute(
            "SELECT * FROM replay_session ORDER BY created_at DESC LIMIT 50"
        ).fetchall()


@router.get("/replay-sessions/{session_id}")
def snapshot(session_id: UUID, _principal=Depends(current_principal)):
    with connection() as conn:
        session = conn.execute("SELECT * FROM replay_session WHERE id=%s", (session_id,)).fetchone()
        if not session:
            raise HTTPException(404, "Replay not found")
        sample = conn.execute(
            "SELECT * FROM telemetry_sample WHERE replay_session_id=%s ORDER BY sequence DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        alerts = conn.execute(
            "SELECT * FROM alert WHERE replay_session_id=%s ORDER BY first_seen_at,id",
            (session_id,),
        ).fetchall()
        for item in alerts:
            item["evidence"] = conn.execute(
                """SELECT ae.*,e.review_state AS current_review_state,e.version AS current_event_version
                FROM alert_evidence ae JOIN drilling_event e ON e.id=ae.event_id WHERE ae.alert_id=%s ORDER BY ae.event_id,ae.passage_id""",
                (item["id"],),
            ).fetchall()
            item["evidence_changed"] = evidence_changed(conn, item["id"])
            item["actions"] = conn.execute(
                "SELECT * FROM alert_action WHERE alert_id=%s ORDER BY recorded_at", (item["id"],)
            ).fetchall()
            item["feedback"] = conn.execute(
                "SELECT * FROM alert_feedback WHERE alert_id=%s ORDER BY recorded_at", (item["id"],)
            ).fetchall()
        worker = conn.execute(
            "SELECT last_seen_at>now()-interval '15 seconds' AS fresh FROM service_heartbeat WHERE service='replay'"
        ).fetchone()
        return {
            "replay_worker_ready": bool(worker and worker["fresh"]),
            "session": session,
            "telemetry": sample,
            "stale": not sample
            or (datetime.now(timezone.utc) - sample["received_at"]).total_seconds() > STALE_SECONDS,
            "alerts": alerts,
            "source_mode": "SIMULATED",
            "lookahead_m": LOOKAHEAD,
            "risk_score": None,
            "risk_reason": "model_not_available",
            "transport": "polling",
            "steps_total": len(DEPTHS),
        }


TRANSITIONS = {
    "acknowledge": ({"NEW"}, "ACKNOWLEDGED"),
    "review": ({"NEW", "ACKNOWLEDGED"}, "UNDER_REVIEW"),
    "resolve": ({"NEW", "ACKNOWLEDGED", "UNDER_REVIEW"}, "RESOLVED"),
    "dismiss": ({"NEW", "ACKNOWLEDGED", "UNDER_REVIEW"}, "DISMISSED"),
    "reopen": ({"RESOLVED", "DISMISSED"}, "UNDER_REVIEW"),
}


@router.post("/alerts/{alert_id}/actions")
def alert_action(
    alert_id: UUID,
    body: Action,
    idempotency_key: str = Header(...),
    principal=Depends(require_role("engineer")),
):
    with connection() as conn:
        digest, old = receipt(
            conn, principal.name, idempotency_key, ["alert_action", alert_id, body.model_dump()]
        )
        if old:
            return old
        alert = conn.execute("SELECT * FROM alert WHERE id=%s FOR UPDATE", (alert_id,)).fetchone()
        if not alert:
            raise HTTPException(404, "Alert not found")
        if alert["revision"] != body.expected_version:
            raise HTTPException(409, "Alert changed; refresh before acting")
        allowed, target = TRANSITIONS[body.action]
        if alert["lifecycle"] not in allowed:
            raise HTTPException(409, "This lifecycle transition is not allowed")
        conn.execute(
            "UPDATE alert SET lifecycle=%s,revision=revision+1 WHERE id=%s", (target, alert_id)
        )
        conn.execute(
            """INSERT INTO alert_action(id,alert_id,actor_name,action,rationale,before_lifecycle,after_lifecycle)
            VALUES(%s,%s,%s,%s,%s,%s,%s)""",
            (
                uuid4(),
                alert_id,
                principal.name,
                body.action,
                body.rationale,
                alert["lifecycle"],
                target,
            ),
        )
        return save_receipt(
            conn,
            principal.name,
            idempotency_key,
            digest,
            {"id": str(alert_id), "lifecycle": target, "revision": alert["revision"] + 1},
        )


@router.post("/alerts/{alert_id}/feedback", status_code=201)
def feedback(
    alert_id: UUID,
    body: Feedback,
    idempotency_key: str = Header(...),
    principal=Depends(require_role("engineer")),
):
    with connection() as conn:
        digest, old = receipt(
            conn, principal.name, idempotency_key, ["feedback", alert_id, body.model_dump()]
        )
        if old:
            return old
        if not conn.execute("SELECT 1 FROM alert WHERE id=%s", (alert_id,)).fetchone():
            raise HTTPException(404, "Alert not found")
        feedback_id = uuid4()
        conn.execute(
            """INSERT INTO alert_feedback(id,alert_id,actor_name,action_taken,observed_outcome,rationale)
            VALUES(%s,%s,%s,%s,%s,%s)""",
            (
                feedback_id,
                alert_id,
                principal.name,
                body.action_taken,
                body.observed_outcome,
                body.rationale,
            ),
        )
        return save_receipt(
            conn,
            principal.name,
            idempotency_key,
            digest,
            {"id": str(feedback_id), "adjudicated_label": None},
        )
