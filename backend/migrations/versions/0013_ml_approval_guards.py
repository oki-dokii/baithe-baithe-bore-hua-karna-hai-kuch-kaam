"""Reject forged identities and mismatched ML approval lineage at the database boundary.

Revision ID: 0013_ml_approval_guards
Revises: 0012_ml_experiment_approval
"""

from alembic import op

revision = "0013_ml_approval_guards"
down_revision = "0012_ml_experiment_approval"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE FUNCTION nwis_check_ml_evidence_submission() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM app_user WHERE username=NEW.prepared_by
                           AND active AND role IN ('engineer','reviewer','admin')) THEN
                RAISE EXCEPTION 'ML preparer must be an active engineer or reviewer'
                    USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER check_ml_evidence_submission
            BEFORE INSERT ON ml_evidence_submission
            FOR EACH ROW EXECUTE FUNCTION nwis_check_ml_evidence_submission();

        CREATE FUNCTION nwis_check_ml_experiment_approval() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE submission ml_evidence_submission%ROWTYPE;
                source_row drilling_parameter_source%ROWTYPE;
        BEGIN
            SELECT * INTO submission FROM ml_evidence_submission
                WHERE id=NEW.submission_id FOR SHARE;
            SELECT * INTO source_row FROM drilling_parameter_source
                WHERE id=NEW.source_id FOR SHARE;
            IF submission.id IS NULL OR source_row.id IS NULL
                OR submission.source_id<>NEW.source_id
                OR submission.evidence_sha256<>NEW.evidence_sha256
                OR submission.prepared_by<>NEW.prepared_by
                OR source_row.source_sha256<>NEW.source_sha256
                OR source_row.qualification_state<>'qualified' THEN
                RAISE EXCEPTION 'ML approval source/submission mismatch or unqualified source'
                    USING ERRCODE='23514';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM app_user WHERE username=NEW.approved_by
                           AND active AND role IN ('reviewer','admin')) THEN
                RAISE EXCEPTION 'ML approver must be an active reviewer'
                    USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER check_ml_experiment_approval
            BEFORE INSERT ON ml_experiment_approval
            FOR EACH ROW EXECUTE FUNCTION nwis_check_ml_experiment_approval();
    """)


def downgrade() -> None:
    raise RuntimeError("ML approval identity guards are retained; restore a backup")
