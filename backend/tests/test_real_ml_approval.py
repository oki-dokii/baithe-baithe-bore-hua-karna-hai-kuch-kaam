import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from psycopg.errors import CheckViolation
from psycopg.types.json import Jsonb

from nwis.db import connection
from nwis.mud_loss_adapter import SourceBundle
from nwis.real_ml_approval import (
    ApprovalError, ApprovalRequest, SubmissionRequest, approve,
    build_source_backed_manifest, canonical_sha256, submit, verify_approval,
)
from nwis.train_mud_loss import demo_manifest, fit_baseline
from nwis.prediction import audit


class Result:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, *, source, submission=None, approval=None, known_events=None,
                 ongoing=False):
        self.source = source
        self.submission = submission
        self.approval = approval
        self.known_events = known_events or []
        self.ongoing = ongoing
        self.writes = []

    def execute(self, sql, args=()):
        if "SELECT src.source_sha256" in sql:
            return Result([self.source])
        if "SELECT * FROM ml_evidence_submission" in sql:
            return Result([self.submission] if self.submission else [])
        if "SELECT * FROM ml_experiment_approval" in sql:
            return Result([self.approval] if self.approval else [])
        if "SELECT actor_name,payload FROM decision_ledger" in sql:
            if not self.approval:
                return Result([])
            return Result([{"actor_name": self.approval["approved_by"], "payload": {
                "manifest_sha256": self.approval["manifest_sha256"],
                "evidence_sha256": self.approval["evidence_sha256"],
                "source_id": str(self.approval["source_id"]),
            }}])
        if "SELECT id FROM drilling_event" in sql:
            return Result(self.known_events)
        if "SELECT 1 FROM drilling_event" in sql:
            return Result([{"?column?": 1}] if self.ongoing else [])
        if "SELECT 1 FROM source_document" in sql:
            return Result([{"?column?": 1}])
        self.writes.append((sql, args))
        if "INSERT INTO ml_experiment_approval" in sql:
            return Result([{"id": args[0]}])
        return Result([])


def fixture():
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    source_id, sample_id, well_id, bore_id, document = (uuid4() for _ in range(5))
    source = {"kind": "public", "source_sha256": "a" * 64,
              "source_reference": "owned real-source test", "permission_reference": "owned test"}
    anchor = {
        "sample_id": str(sample_id), "physical_well_id": str(well_id),
        "wellbore_id": str(bore_id), "split": "train", "observed_at": now,
        "available_at": now + timedelta(seconds=2), "md_m": 500,
        "quality": "good", "rig_state": "forward_drilling", "source_record_id": "row-1",
        "features": {"rop_m_per_h": 9, "wob_kn": 45, "rpm": 100,
                     "torque_kn_m": 8, "flow_in_l_per_min": 1000},
    }
    bundle = SourceBundle.model_validate({
        "schema_version": "mud-loss-adapter-input-v1", "kind": "public",
        **{key: source[key] for key in ("source_sha256", "source_reference", "permission_reference")},
        "domain_reviewed": True, "anchors": [anchor],
        "mud_density": [{"wellbore_id": str(bore_id),
                         "source_record_id": f"document:{document}",
                         "source_kind": "reviewed_mud_program",
                         "recorded_at": now - timedelta(days=1),
                         "effective_from": now - timedelta(days=1),
                         "top_md_m": 400, "base_md_m": 700,
                         "mud_density_kg_per_m3": 1200, "reviewed": True}],
        "coverage": [{"wellbore_id": str(bore_id),
                      "source_reference": f"document:{document}",
                      "top_md_m": 400, "base_md_m": 600,
                      "from_time": now - timedelta(hours=1),
                      "observed_through_at": now + timedelta(hours=1),
                      "reviewed": True, "event_free_reviewed": True}],
        "losses": [],
    })
    row = {"sample_id": sample_id, "physical_well_id": well_id,
           "wellbore_id": bore_id, "source_record_id": "row-1",
           "observed_at": now, "available_at": now + timedelta(seconds=2),
           "md_m": Decimal(500), **{key: Decimal(value) for key, value in anchor["features"].items()}}
    return source_id, source, row, bundle


def test_source_backed_join_and_omitted_event_fail_closed(monkeypatch):
    source_id, source, row, bundle = fixture()
    monkeypatch.setattr("nwis.real_ml_approval.eligible_anchors", lambda _conn, _id: [row])
    manifest = build_source_backed_manifest(FakeConnection(source=source), source_id, bundle)
    assert manifest.windows[0].label == 0
    altered = bundle.model_copy(deep=True)
    altered.anchors[0].features["wob_kn"] = 99
    with pytest.raises(ApprovalError, match="anchor_differs_from_qualified_source_row"):
        build_source_backed_manifest(FakeConnection(source=source), source_id, altered)
    with pytest.raises(ApprovalError, match="approved_loss_omitted"):
        build_source_backed_manifest(
            FakeConnection(source=source, known_events=[{"id": uuid4()}]), source_id, bundle
        )
    with pytest.raises(ApprovalError, match="loss_ongoing_at_anchor"):
        build_source_backed_manifest(FakeConnection(source=source, ongoing=True), source_id, bundle)


def test_authenticated_submission_identity_and_review_gate(monkeypatch):
    source_id, source, row, bundle = fixture()
    monkeypatch.setattr("nwis.real_ml_approval.eligible_anchors", lambda _conn, _id: [row])
    monkeypatch.setattr("nwis.real_ml_approval.append_decision", lambda *args, **kwargs: 1)
    conn = FakeConnection(source=source)
    result = submit(conn, SubmissionRequest(source_id=source_id, evidence=bundle), "engineer-a")
    assert result["approved"] is False
    assert any("INSERT INTO ml_evidence_submission" in sql for sql, _ in conn.writes)
    conn.submission = {"source_id": source_id, "prepared_by": "engineer-a",
                       "evidence_sha256": canonical_sha256(bundle.model_dump(mode="json"))}
    request = ApprovalRequest(submission_id=result["submission_id"],
                              review_reference="signed review note 1", evidence=bundle)
    with pytest.raises(ApprovalError, match="independent_reviewer_required"):
        approve(conn, request, "engineer-a")
    changed = bundle.model_copy(deep=True)
    changed.coverage[0].event_free_reviewed = False
    with pytest.raises(ApprovalError, match="submitted_evidence_changed"):
        approve(conn, request.model_copy(update={"evidence": changed}), "reviewer-b")
    # A single-well fixture is intentionally inadequate for approval.
    with pytest.raises(ApprovalError, match="manifest_structure_gate_failed"):
        approve(conn, request, "reviewer-b")
    assert not any("INSERT INTO ml_experiment_approval" in sql for sql, _ in conn.writes)


def test_approval_binds_exact_bundle_and_offline_training_only(monkeypatch):
    source_id, source, _row, bundle = fixture()
    test_manifest = demo_manifest().model_copy(
        update={"kind": "public", "domain_reviewed": True,
                "source_sha256": bundle.source_sha256}
    )
    monkeypatch.setattr(
        "nwis.real_ml_approval.build_source_backed_manifest",
        lambda _conn, _source_id, _bundle: test_manifest,
    )
    monkeypatch.setattr("nwis.real_ml_approval.append_decision", lambda *args, **kwargs: 1)
    monkeypatch.setattr("nwis.real_ml_approval.verify_decision_chain",
                        lambda _conn: {"ok": True})
    submission_id, approval_id = uuid4(), uuid4()
    evidence_sha = canonical_sha256(bundle.model_dump(mode="json"))
    conn = FakeConnection(source=source, submission={
        "source_id": source_id, "prepared_by": "engineer-a", "evidence_sha256": evidence_sha,
    })
    result = approve(conn, ApprovalRequest(
        submission_id=submission_id, review_reference="signed domain review",
        evidence=bundle,
    ), "reviewer-b")
    assert result["scope"] == "offline_experiment_only"
    assert result["training_run_started"] is False
    assert result["operationally_validated"] is False
    conn.approval = {"id": approval_id, "source_id": source_id,
                     "approval_scope": "offline_experiment_only",
                     "approved_by": "reviewer-b",
                     "evidence_sha256": evidence_sha,
                     "manifest_sha256": audit(test_manifest)["manifest_sha256"],
                     "source_sha256": bundle.source_sha256}
    manifest, verified = verify_approval(conn, approval_id, source_id, bundle)
    artifact, card = fit_baseline(manifest, audit(manifest),
                                  state="offline_real_experiment_only",
                                  training_authorized=True,
                                  approval_id=verified["approval_id"])
    assert artifact["approval_id"] == str(approval_id)
    assert card["training_authorized"] is True
    assert card["deployed"] is False
    changed = bundle.model_copy(deep=True)
    changed.coverage[0].event_free_reviewed = False
    with pytest.raises(ApprovalError, match="approved_evidence_changed"):
        verify_approval(conn, approval_id, source_id, changed)


@pytest.mark.skipif(os.getenv("NWIS_INTEGRATION") != "1", reason="Needs initialized NWIS test DB")
def test_database_rejects_unqualified_or_mutable_approval():
    dataset_id, source_id, submission_id, approval_id = (uuid4() for _ in range(4))
    with connection() as conn:
        users = conn.execute(
            "SELECT username,role FROM app_user WHERE active ORDER BY username"
        ).fetchall()
        reviewer = next((u["username"] for u in users if u["role"] in ("reviewer", "admin")), None)
        preparer = next((u["username"] for u in users if u["username"] != reviewer and
                         u["role"] in ("engineer", "reviewer", "admin")), None)
        if not reviewer or not preparer:
            pytest.skip("Needs two distinct configured local users, including a reviewer")
        conn.execute(
            """INSERT INTO dataset(id,external_id,name,kind,version,qualification_status,
               origin_kind,authorization_state,applicability)
               VALUES (%s,%s,'Owned approval fixture','public','1','qualified',
                       'public_primary','public_permitted','analog_only')""",
            (dataset_id, f"owned-ml-approval-{dataset_id}"),
        )
        conn.execute(
            """INSERT INTO drilling_parameter_source
               (id,dataset_id,external_id,source_sha256,source_kind,source_reference,
                permission_reference,source_timezone,md_datum,source_units,mapping_version,
                mapping_evidence)
               VALUES (%s,%s,'owned-test-source',%s,'csv_export','owned test','owned test',
                       'UTC','KB',%s,'test-v1',%s)""",
            (source_id, dataset_id, "a" * 64, Jsonb({"md": "m"}), Jsonb({
                "unit_reference": "owned", "depth_semantics_reference": "owned",
                "availability_reference": "owned", "availability_policy": "owned",
                "rig_state_basis": "owned", "selection_start_at": "2025-01-01T00:00:00Z",
                "selection_end_at": "2025-01-02T00:00:00Z",
                "receipt_at": "2025-01-03T00:00:00Z",
            })),
        )
        conn.execute(
            """INSERT INTO ml_evidence_submission
               (id,source_id,evidence_sha256,prepared_by) VALUES (%s,%s,%s,%s)""",
            (submission_id, source_id, "b" * 64, preparer),
        )
        insert = """INSERT INTO ml_experiment_approval
            (id,submission_id,source_id,manifest_sha256,evidence_sha256,
             source_sha256,prepared_by,approved_by,review_reference)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'owned signed review')"""
        args = (approval_id, submission_id, source_id, "c" * 64, "b" * 64,
                "a" * 64, preparer, reviewer)
        with pytest.raises(CheckViolation):
            with conn.transaction():
                conn.execute(insert, args)
        conn.execute(
            """UPDATE drilling_parameter_source SET units_reviewed=true,
               timezone_reviewed=true, datum_reviewed=true, rig_state_reviewed=true,
               qualification_state='qualified',qualified_by=%s,qualified_at=now()
               WHERE id=%s""",
            (reviewer, source_id),
        )
        conn.execute(insert, args)
        with pytest.raises(CheckViolation):
            with conn.transaction():
                conn.execute("UPDATE ml_experiment_approval SET review_reference='changed' WHERE id=%s",
                             (approval_id,))
        conn.rollback()
