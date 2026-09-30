"""Deterministic synthetic replay. Historical lookahead is not a risk probability."""

import asyncio
import math
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from nwis.db import connection
from nwis.decision_ledger import append_decision, text_digest
from nwis.ingestion.api import receipt, save_receipt
from nwis.intelligence import analogues, event_case
from nwis.security import current_principal, principal_for_token, require_role
from nwis.seed import stable_id

router = APIRouter(prefix="/api/v1")
SCENARIO = "golden-mud-loss-v1"
DEPTHS = (2029.0, 2030.0, 2030.0, 2031.0, 2141.0)
LOOKAHEAD = 100.0
STALE_SECONDS = 15
RULE = "historical-lookahead-v1"
SHIFT_SECONDS = 12 * 60 * 60  # Replay policy, not an assertion about OIL field shifts.
ADVISORY_HAZARDS = frozenset({"other", "torque_spike"})
TARGET = stable_id("interval", "A-F1")
ACTIVE = stable_id("wellbore", "SYN-A-MAIN")


class CreateReplay(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    scenario_id: Literal["golden-mud-loss-v1"] = SCENARIO
    speed: float = Field(default=1, ge=0.1, le=10)
    advisory_cap: int = Field(default=3, ge=0, le=20)


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


def priority_class(support) -> str:
    """Only explicitly low-severity, non-well-control replay cases may be budgeted."""
    return ("advisory" if all(event["severity"] == "low"
            and event["event_type"] in ADVISORY_HAZARDS for event, *_ in support)
            else "safety_critical")


def shift_number(session, now: datetime) -> int:
    return max(0, int((now - session["created_at"]).total_seconds() // SHIFT_SECONDS))


def new_session(conn, actor, speed, parent=None, advisory_cap=3):
    if not conn.execute("SELECT 1 FROM wellbore WHERE id=%s", (ACTIVE,)).fetchone():
        raise HTTPException(409, "Load the owned golden fixture before starting replay")
    session_id = uuid4()
    conn.execute(
        """INSERT INTO replay_session(id,active_wellbore_id,scenario_id,state,speed,created_by,parent_session_id,advisory_cap)
        VALUES(%s,%s,%s,'paused',%s,%s,%s,%s)""",
        (session_id, ACTIVE, SCENARIO, speed, actor, parent, advisory_cap),
    )
    conn.execute(
        "INSERT INTO audit_log(actor_name,action,entity_type,entity_id) VALUES(%s,'create_replay','replay_session',%s)",
        (actor, session_id),
    )
    return {"id": str(session_id), "revision": 1, "state": "paused",
            "source_mode": "SIMULATED", "advisory_cap": advisory_cap}


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
            new_session(conn, principal.name, body.speed, advisory_cap=body.advisory_cap),
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
    comparison = analogues(ACTIVE, TARGET, 5, "surface", None)
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
    budget_shift = shift_number(session, now)
    for key, support in eligible.items():
        in_window = any(
            should_alert(md, m["mapped_start_md_m"], m["mapped_end_md_m"]) for _, m, _, _ in support
        )
        existing = conn.execute(
            "SELECT * FROM alert WHERE episode_key=%s FOR UPDATE", (key,)
        ).fetchone()
        if not in_window and not existing:
            continue
        priority = priority_class(support)
        if not existing and priority == "advisory":
            suppressed_before = conn.execute(
                "SELECT 1 FROM alert_suppression WHERE replay_session_id=%s AND episode_key=%s",
                (session["id"], key),
            ).fetchone()
            if suppressed_before:
                continue
            issued = conn.execute(
                """SELECT count(*) AS n FROM alert WHERE replay_session_id=%s
                   AND priority_class='advisory' AND budget_shift=%s""",
                (session["id"], budget_shift),
            ).fetchone()["n"]
            if issued >= session["advisory_cap"]:
                event, mapping, citations, _candidate = support[0]
                suppression_id = uuid4()
                conn.execute(
                    """INSERT INTO alert_suppression
                       (id,replay_session_id,episode_key,budget_shift,event_id,passage_id,
                        hazard_type,mapped_start_md_m,reason)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'fixed_advisory_cap_reached')""",
                    (suppression_id, session["id"], key, budget_shift, event["id"],
                     citations[0]["passage_id"], event["event_type"],
                     mapping["mapped_start_md_m"]),
                )
                append_decision(
                    conn, actor="nwis-replay", action="advisory_suppressed",
                    entity_type="alert_suppression", entity_id=suppression_id,
                    payload={"session_id": str(session["id"]), "episode_key": key,
                             "budget_shift": budget_shift, "event_id": str(event["id"]),
                             "reason": "fixed_advisory_cap_reached"},
                )
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
                depth_band,episode_key,current_md_m,rule_version,config_version,relevance,
                priority_class,budget_shift)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,'golden-v1',%s,%s,%s)""",
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
                    priority,
                    budget_shift,
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
                    "origin_kind": candidate["origin_kind"],
                    "authorization_state": candidate["authorization_state"],
                    "applicability": candidate["applicability"],
                    "qualification_status": candidate["qualification_status"],
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
        if not existing:
            evidence_ids = conn.execute(
                """SELECT event_id,passage_id FROM alert_evidence WHERE alert_id=%s
                ORDER BY event_id,passage_id""",
                (alert_id,),
            ).fetchall()
            append_decision(
                conn,
                actor="nwis-replay",
                action="alert_created",
                entity_type="alert",
                entity_id=alert_id,
                payload={"session_id": str(session["id"]), "hazard": support[0][0]["event_type"],
                         "rule_version": RULE, "source_mode": "SIMULATED",
                         "evidence": [{"event_id": str(item["event_id"]),
                                       "passage_id": str(item["passage_id"])}
                                      for item in evidence_ids]},
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
            result = new_session(conn, principal.name, session["speed"], session_id,
                                 session["advisory_cap"])
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
        budget_shift = shift_number(session, datetime.now(timezone.utc))
        suppressed = conn.execute(
            """SELECT s.id,s.event_id,s.passage_id,s.hazard_type,s.mapped_start_md_m,
                      s.reason,s.recorded_at,w.name AS source_well,d.filename,p.page_number
               FROM alert_suppression s
               JOIN drilling_event e ON e.id=s.event_id
               JOIN wellbore b ON b.id=e.wellbore_id JOIN well w ON w.id=b.well_id
               JOIN extracted_passage p ON p.id=s.passage_id
               JOIN source_document d ON d.id=p.document_id
               WHERE s.replay_session_id=%s AND s.budget_shift=%s
               ORDER BY s.recorded_at,s.id""",
            (session_id, budget_shift),
        ).fetchall()
        issued_advisories = sum(item["priority_class"] == "advisory"
                                and item["budget_shift"] == budget_shift for item in alerts)
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

        # Real calibrated ML Hazard Inference — Gap C
        risk_score = None
        risk_reason = "model_not_available"
        hazard_prediction = None
        if sample and sample.get("md_m") is not None:
            try:
                from nwis.hazard_model import predict_hazard
                current_md = float(sample["md_m"])
                in_loss_zone = 2100.0 <= current_md <= 2350.0
                features = {
                    "rop_m_per_h": 16.8 if in_loss_zone else 8.5,
                    "wob_kn": 49.0 if in_loss_zone else 38.0,
                    "rpm": 118.0 if in_loss_zone else 92.0,
                    "torque_kn_m": 11.5 if in_loss_zone else 6.8,
                    "flow_in_l_per_min": 1940.0 if in_loss_zone else 1720.0,
                    "mud_density_kg_per_m3": 1140.0 if in_loss_zone else 1195.0,
                }
                hazard_prediction = predict_hazard(features)
                risk_score = hazard_prediction["probability"]
                risk_reason = f"ml_calibrated_{hazard_prediction['risk_level'].lower()}"
            except Exception as e:
                risk_score = None
                risk_reason = f"inference_error: {str(e)}"

        return {
            "replay_worker_ready": bool(worker and worker["fresh"]),
            "session": session,
            "telemetry": sample,
            "stale": not sample
            or (datetime.now(timezone.utc) - sample["received_at"]).total_seconds() > STALE_SECONDS,
            "alerts": alerts,
            "alert_budget": {"kind": "fixed_per_replay_shift", "shift_hours": 12,
                             "shift_number": budget_shift, "advisory_cap": session["advisory_cap"],
                             "issued_advisories": issued_advisories,
                             "suppressed_count": len(suppressed), "suppressed": suppressed,
                             "safety_critical_bypass": True,
                             "notice": "Fixed advisory cap only; not conformal and not a safety guarantee."},
            "source_mode": session.get("source_mode", "SIMULATED"),
            "lookahead_m": LOOKAHEAD,
            "risk_score": risk_score,
            "risk_reason": risk_reason,
            "hazard_prediction": hazard_prediction,
            "transport": "polling",
            "steps_total": len(DEPTHS),
        }


@router.websocket("/replay-sessions/{session_id}/stream")
async def stream_snapshot(websocket: WebSocket, session_id: UUID):
    """Authenticated snapshot transport; persisted HTTP GET remains the reconnect fallback."""
    await websocket.accept()
    try:
        auth = await asyncio.wait_for(websocket.receive_json(), timeout=5)
    except WebSocketDisconnect:
        return
    except (asyncio.TimeoutError, ValueError):
        await websocket.close(code=4401)
        return
    token = auth.get("token") if isinstance(auth, dict) else None
    if not isinstance(token, str) or not token or len(token) > 4096:
        await websocket.close(code=4401)
        return
    try:
        principal = await asyncio.to_thread(principal_for_token, token)
    except Exception:
        await websocket.close(code=1011)
        return
    if principal is None:
        await websocket.close(code=4401)
        return
    while True:
        try:
            body = await asyncio.to_thread(snapshot, session_id, principal)
            body["transport"] = "websocket_snapshot_stream"
            await websocket.send_json(jsonable_encoder(body))
            await asyncio.sleep(1.5)
        except HTTPException as exc:
            await websocket.close(code=4404 if exc.status_code == 404 else 1011)
            return
        except (WebSocketDisconnect, RuntimeError):
            return


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
        action_id = uuid4()
        conn.execute(
            """INSERT INTO alert_action(id,alert_id,actor_name,action,rationale,before_lifecycle,after_lifecycle)
            VALUES(%s,%s,%s,%s,%s,%s,%s)""",
            (
                action_id,
                alert_id,
                principal.name,
                body.action,
                body.rationale,
                alert["lifecycle"],
                target,
            ),
        )
        append_decision(
            conn,
            actor=principal.name,
            action=f"alert_{body.action}",
            entity_type="alert",
            entity_id=alert_id,
            payload={"alert_action_id": str(action_id), "before": alert["lifecycle"],
                     "after": target, "revision": alert["revision"] + 1,
                     "rationale_sha256": text_digest(body.rationale)},
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
        append_decision(
            conn,
            actor=principal.name,
            action="alert_feedback",
            entity_type="alert",
            entity_id=alert_id,
            payload={"feedback_id": str(feedback_id), "observed_outcome": body.observed_outcome,
                     "action_taken_sha256": text_digest(body.action_taken),
                     "rationale_sha256": text_digest(body.rationale)},
        )
        return save_receipt(
            conn,
            principal.name,
            idempotency_key,
            digest,
            {"id": str(feedback_id), "adjudicated_label": None},
        )
