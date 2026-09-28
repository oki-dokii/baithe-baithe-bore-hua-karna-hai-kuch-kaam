"""Immutable, experiment-scoped approval of a reviewed mud-loss manifest.

Revision ID: 0012_ml_experiment_approval
Revises: 0011_source_mapping_review
"""

from alembic import op

revision = "0012_ml_experiment_approval"
down_revision = "0011_source_mapping_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE ml_evidence_submission (
            id uuid PRIMARY KEY,
            source_id uuid NOT NULL REFERENCES drilling_parameter_source(id) ON DELETE RESTRICT,
            evidence_sha256 text NOT NULL CHECK (evidence_sha256 ~ '^[0-9a-f]{64}$'),
            prepared_by text NOT NULL CHECK (length(btrim(prepared_by)) > 0),
            submitted_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE ml_experiment_approval (
            id uuid PRIMARY KEY,
            submission_id uuid NOT NULL UNIQUE REFERENCES ml_evidence_submission(id) ON DELETE RESTRICT,
            source_id uuid NOT NULL REFERENCES drilling_parameter_source(id) ON DELETE RESTRICT,
            manifest_sha256 text NOT NULL UNIQUE CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
            evidence_sha256 text NOT NULL CHECK (evidence_sha256 ~ '^[0-9a-f]{64}$'),
            source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
            prepared_by text NOT NULL CHECK (length(btrim(prepared_by)) > 0),
            approved_by text NOT NULL CHECK (length(btrim(approved_by)) > 0),
            review_reference text NOT NULL CHECK (length(btrim(review_reference)) > 0),
            approval_scope text NOT NULL DEFAULT 'offline_experiment_only'
                CHECK (approval_scope = 'offline_experiment_only'),
            approved_at timestamptz NOT NULL DEFAULT now(),
            CHECK (prepared_by <> approved_by)
        );
        CREATE FUNCTION nwis_reject_ml_approval_change() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'ML experiment approvals are append-only' USING ERRCODE='23514';
        END $$;
        CREATE TRIGGER immutable_ml_experiment_approval
            BEFORE UPDATE OR DELETE ON ml_experiment_approval
            FOR EACH ROW EXECUTE FUNCTION nwis_reject_ml_approval_change();
        CREATE TRIGGER immutable_ml_experiment_approval_truncate
            BEFORE TRUNCATE ON ml_experiment_approval
            FOR EACH STATEMENT EXECUTE FUNCTION nwis_reject_ml_approval_change();
        CREATE TRIGGER immutable_ml_evidence_submission
            BEFORE UPDATE OR DELETE ON ml_evidence_submission
            FOR EACH ROW EXECUTE FUNCTION nwis_reject_ml_approval_change();
        CREATE TRIGGER immutable_ml_evidence_submission_truncate
            BEFORE TRUNCATE ON ml_evidence_submission
            FOR EACH STATEMENT EXECUTE FUNCTION nwis_reject_ml_approval_change();
    """)


def downgrade() -> None:
    raise RuntimeError("Experiment approvals are retained; restore a backup")
