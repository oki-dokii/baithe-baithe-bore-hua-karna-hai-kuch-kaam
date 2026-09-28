"""Qualified-source join and independent, offline-only ML experiment approval.

The reviewed coverage and mud-program assertions remain human attestations;
document linkage proves provenance, not that their interpretations are correct.
"""

import hashlib
import json
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from nwis.db import connection
from nwis.decision_ledger import append_decision, verify as verify_decision_chain
from nwis.drilling_parameters import eligible_anchors
from nwis.mud_loss_adapter import AdapterError, SourceBundle, build_manifest
from nwis.prediction import DatasetManifest, audit
from nwis.security import Principal, require_role

router = APIRouter(prefix="/api/v1")
SENSOR_NAMES = ("rop_m_per_h", "wob_kn", "rpm", "torque_kn_m", "flow_in_l_per_min")


class SubmissionRequest(BaseModel):
    source_id: UUID
    evidence: SourceBundle


class ApprovalRequest(BaseModel):
    submission_id: UUID
    review_reference: str = Field(min_length=1, pattern=r"\S")
    evidence: SourceBundle


class ApprovalError(ValueError):
    pass


def canonical_sha256(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def document_id(reference: str) -> UUID:
    try:
        prefix, raw_id = reference.split(":", 1)
        if prefix != "document":
            raise ValueError
        return UUID(raw_id)
    except ValueError as exc:
        raise ApprovalError("reviewed_evidence_requires_document_uuid_reference") from exc


def validate_document(conn, reference: str, wellbore_id: str) -> None:
    try:
        bore_id = UUID(wellbore_id)
    except ValueError as exc:
        raise ApprovalError("evidence_requires_database_wellbore_id") from exc
    row = conn.execute(
        """SELECT 1 FROM source_document d
           JOIN document_wellbore dw ON dw.document_id=d.id
           JOIN wellbore b ON b.id=dw.wellbore_id
           JOIN well w ON w.id=b.well_id
           JOIN dataset ds ON ds.id=w.dataset_id AND ds.id=d.dataset_id
           WHERE d.id=%s AND dw.wellbore_id=%s""",
        (document_id(reference), bore_id),
    ).fetchone()
    if not row:
        raise ApprovalError("reviewed_evidence_document_not_linked_to_wellbore")


def build_source_backed_manifest(conn, source_id: UUID, bundle: SourceBundle) -> DatasetManifest:
    source = conn.execute(
        """SELECT src.source_sha256,src.source_reference,src.permission_reference,
                  d.kind FROM drilling_parameter_source src
           JOIN dataset d ON d.id=src.dataset_id WHERE src.id=%s""",
        (source_id,),
    ).fetchone()
    if not source or source["kind"] not in ("public", "private"):
        raise ApprovalError("qualified_real_source_required")
    if bundle.kind != source["kind"] or any(
        getattr(bundle, field) != source[field]
        for field in ("source_sha256", "source_reference", "permission_reference")
    ):
        raise ApprovalError("evidence_source_identity_mismatch")
    qualified = {str(row["sample_id"]): row for row in eligible_anchors(conn, source_id)}
    for anchor in bundle.anchors:
        row = qualified.get(anchor.sample_id)
        if not row:
            raise ApprovalError("anchor_not_current_qualified_sample")
        if (
            anchor.physical_well_id != str(row["physical_well_id"])
            or anchor.wellbore_id != str(row["wellbore_id"])
            or anchor.source_record_id != row["source_record_id"]
            or anchor.observed_at != row["observed_at"]
            or anchor.available_at != row["available_at"]
            or anchor.md_m != float(row["md_m"])
            or any(anchor.features[name] != float(row[name]) for name in SENSOR_NAMES)
        ):
            raise ApprovalError("anchor_differs_from_qualified_source_row")
    for density in bundle.mud_density:
        if density.source_kind != "reviewed_mud_program" or not density.reviewed:
            raise ApprovalError("reviewed_document_mud_density_required")
        validate_document(conn, density.source_record_id, density.wellbore_id)
    for coverage in bundle.coverage:
        if not coverage.reviewed:
            raise ApprovalError("coverage_review_required")
        validate_document(conn, coverage.source_reference, coverage.wellbore_id)
    for loss in bundle.losses:
        if not loss.event_reviewed or not loss.depth_datum_reviewed:
            raise ApprovalError("loss_review_required")
        try:
            event_id, passage_id, bore_id = (
                UUID(loss.event_id), UUID(loss.source_passage_id), UUID(loss.wellbore_id)
            )
        except ValueError as exc:
            raise ApprovalError("loss_requires_database_event_and_passage_ids") from exc
        event = conn.execute(
            """SELECT e.start_md_m,e.onset_time_earliest,e.onset_time_latest,
                      e.onset_time_basis FROM drilling_event e
               JOIN event_passage ep ON ep.event_id=e.id
               WHERE e.id=%s AND ep.passage_id=%s AND e.wellbore_id=%s
                 AND e.event_type='mud_loss' AND e.review_state='approved'""",
            (event_id, passage_id, bore_id),
        ).fetchone()
        if not event or event["start_md_m"] is None or (
            float(event["start_md_m"]) != loss.onset_md_m
            or event["onset_time_earliest"] != loss.onset_earliest
            or event["onset_time_latest"] != loss.onset_latest
            or event["onset_time_basis"] != loss.onset_basis
        ):
            raise ApprovalError("loss_does_not_match_approved_cited_event")
    supplied_events = {loss.event_id for loss in bundle.losses}
    for anchor in bundle.anchors:
        ongoing = conn.execute(
            """SELECT 1 FROM drilling_event WHERE wellbore_id=%s
               AND event_type='mud_loss' AND review_state='approved'
               AND start_md_m <= %s AND (end_md_m IS NULL OR end_md_m >= %s)
               LIMIT 1""",
            (UUID(anchor.wellbore_id), anchor.md_m, anchor.md_m),
        ).fetchone()
        if ongoing:
            raise ApprovalError("loss_ongoing_at_anchor")
        # An omitted approved event must never turn an interval into a negative.
        known = conn.execute(
            """SELECT id FROM drilling_event WHERE wellbore_id=%s
               AND event_type='mud_loss' AND review_state='approved'
               AND (start_md_m IS NULL OR
                    (start_md_m > %s AND start_md_m <= %s))""",
            (UUID(anchor.wellbore_id), anchor.md_m, anchor.md_m + 100),
        ).fetchall()
        if any(str(row["id"]) not in supplied_events for row in known):
            raise ApprovalError("approved_loss_omitted_from_outcome_window")
    return build_manifest(bundle)


def submit(conn, request: SubmissionRequest, preparer: str) -> dict:
    build_source_backed_manifest(conn, request.source_id, request.evidence)
    evidence_sha = canonical_sha256(request.evidence.model_dump(mode="json"))
    submission_id = uuid4()
    conn.execute(
        """INSERT INTO ml_evidence_submission(id,source_id,evidence_sha256,prepared_by)
           VALUES (%s,%s,%s,%s)""",
        (submission_id, request.source_id, evidence_sha, preparer),
    )
    append_decision(
        conn, actor=preparer, action="submit_ml_evidence",
        entity_type="ml_evidence_submission", entity_id=submission_id,
        payload={"evidence_sha256": evidence_sha, "source_id": str(request.source_id)},
    )
    return {"submission_id": str(submission_id), "evidence_sha256": evidence_sha,
            "approved": False}


def approve(conn, request: ApprovalRequest, reviewer: str) -> dict:
    submission = conn.execute(
        "SELECT * FROM ml_evidence_submission WHERE id=%s", (request.submission_id,)
    ).fetchone()
    if not submission:
        raise ApprovalError("evidence_submission_missing")
    if reviewer == submission["prepared_by"]:
        raise ApprovalError("independent_reviewer_required")
    if not request.evidence.domain_reviewed:
        raise ApprovalError("domain_review_required")
    evidence_sha = canonical_sha256(request.evidence.model_dump(mode="json"))
    if evidence_sha != submission["evidence_sha256"]:
        raise ApprovalError("submitted_evidence_changed")
    manifest = build_source_backed_manifest(conn, submission["source_id"], request.evidence)
    report = audit(manifest)
    if report["blockers"]:
        raise ApprovalError("manifest_structure_gate_failed:" + ",".join(report["blockers"]))
    approval_id = uuid4()
    inserted = conn.execute(
        """INSERT INTO ml_experiment_approval
           (id,submission_id,source_id,manifest_sha256,evidence_sha256,source_sha256,
            prepared_by,approved_by,review_reference)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT DO NOTHING RETURNING id""",
        (approval_id, request.submission_id, submission["source_id"],
         report["manifest_sha256"], evidence_sha, manifest.source_sha256,
         submission["prepared_by"], reviewer, request.review_reference),
    ).fetchone()
    if not inserted:
        raise ApprovalError("experiment_approval_already_exists")
    append_decision(
        conn, actor=reviewer, action="approve_offline_ml_experiment",
        entity_type="ml_experiment_approval", entity_id=approval_id,
        payload={"manifest_sha256": report["manifest_sha256"],
                 "evidence_sha256": evidence_sha, "source_id": str(submission["source_id"]),
                 "submission_id": str(request.submission_id),
                 "scope": "offline_experiment_only"},
    )
    return {"approval_id": str(approval_id), "manifest_sha256": report["manifest_sha256"],
            "evidence_sha256": evidence_sha, "scope": "offline_experiment_only",
            "training_run_started": False, "operationally_validated": False}


def verify_approval(
    conn, approval_id: UUID, source_id: UUID, bundle: SourceBundle,
) -> tuple[DatasetManifest, dict]:
    record = conn.execute(
        "SELECT * FROM ml_experiment_approval WHERE id=%s", (approval_id,)
    ).fetchone()
    if not record or record["approval_scope"] != "offline_experiment_only":
        raise ApprovalError("experiment_approval_missing")
    ledger = conn.execute(
        """SELECT actor_name,payload FROM decision_ledger
           WHERE entity_type='ml_experiment_approval' AND entity_id=%s
             AND action='approve_offline_ml_experiment'""",
        (approval_id,),
    ).fetchall()
    if len(ledger) != 1 or ledger[0]["actor_name"] != record["approved_by"] or (
        ledger[0]["payload"].get("manifest_sha256") != record["manifest_sha256"]
        or ledger[0]["payload"].get("evidence_sha256") != record["evidence_sha256"]
        or ledger[0]["payload"].get("source_id") != str(record["source_id"])
    ) or not verify_decision_chain(conn)["ok"]:
        raise ApprovalError("approval_decision_ledger_invalid")
    if record["source_id"] != source_id:
        raise ApprovalError("approved_source_mismatch")
    if canonical_sha256(bundle.model_dump(mode="json")) != record["evidence_sha256"]:
        raise ApprovalError("approved_evidence_changed")
    manifest = build_source_backed_manifest(conn, source_id, bundle)
    report = audit(manifest)
    if (
        manifest.kind == "synthetic" or report["blockers"]
        or report["manifest_sha256"] != record["manifest_sha256"]
        or manifest.source_sha256 != record["source_sha256"]
    ):
        raise ApprovalError("approved_manifest_mismatch_or_failed_audit")
    return manifest, {"approval_id": str(approval_id), "scope": record["approval_scope"],
                      "manifest_sha256": report["manifest_sha256"]}


@router.post("/ml/experiments/approve", status_code=201)
def approve_experiment(
    request: ApprovalRequest, principal: Principal = Depends(require_role("reviewer")),
):
    try:
        with connection() as conn:
            return approve(conn, request, principal.name)
    except (ApprovalError, AdapterError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/ml/evidence/submit", status_code=201)
def submit_evidence(
    request: SubmissionRequest, principal: Principal = Depends(require_role("engineer", "reviewer")),
):
    try:
        with connection() as conn:
            return submit(conn, request, principal.name)
    except (ApprovalError, AdapterError) as exc:
        raise HTTPException(422, str(exc)) from exc
