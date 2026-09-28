"""Replay-only fixed advisory budget with an inspectable suppression digest.

Revision ID: 0014_alert_budget
Revises: 0013_ml_approval_guards
"""

from alembic import op

revision = "0014_alert_budget"
down_revision = "0013_ml_approval_guards"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE replay_session ADD COLUMN advisory_cap integer NOT NULL DEFAULT 3
            CHECK (advisory_cap BETWEEN 0 AND 20);
        ALTER TABLE alert ADD COLUMN priority_class text NOT NULL DEFAULT 'safety_critical'
            CHECK (priority_class IN ('safety_critical','advisory'));
        ALTER TABLE alert ADD COLUMN budget_shift integer NOT NULL DEFAULT 0
            CHECK (budget_shift >= 0);
        CREATE TABLE alert_suppression (
            id uuid PRIMARY KEY,
            replay_session_id uuid NOT NULL REFERENCES replay_session(id) ON DELETE RESTRICT,
            episode_key text NOT NULL,
            budget_shift integer NOT NULL CHECK (budget_shift >= 0),
            event_id uuid NOT NULL REFERENCES drilling_event(id) ON DELETE RESTRICT,
            passage_id uuid NOT NULL REFERENCES extracted_passage(id) ON DELETE RESTRICT,
            hazard_type text NOT NULL,
            mapped_start_md_m numeric NOT NULL CHECK (mapped_start_md_m >= 0),
            reason text NOT NULL CHECK (reason='fixed_advisory_cap_reached'),
            recorded_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (replay_session_id,episode_key)
        );
        CREATE FUNCTION nwis_reject_alert_suppression_change() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Alert suppression history is append-only' USING ERRCODE='23514';
        END $$;
        CREATE TRIGGER immutable_alert_suppression BEFORE UPDATE OR DELETE ON alert_suppression
            FOR EACH ROW EXECUTE FUNCTION nwis_reject_alert_suppression_change();
        CREATE TRIGGER immutable_alert_suppression_truncate BEFORE TRUNCATE ON alert_suppression
            FOR EACH STATEMENT EXECUTE FUNCTION nwis_reject_alert_suppression_change();
    """)


def downgrade() -> None:
    raise RuntimeError("Alert-budget decisions are retained; restore a backup")
