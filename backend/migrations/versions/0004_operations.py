"""Versioned synthetic replay and immutable alert actions."""

from alembic import op

revision = "0004_operations"
down_revision = "0003_document_ingestion"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE replay_session ADD COLUMN revision integer NOT NULL DEFAULT 1;
        ALTER TABLE replay_session ADD COLUMN next_sequence integer NOT NULL DEFAULT 0;
        ALTER TABLE replay_session ADD COLUMN next_tick_at timestamptz NOT NULL DEFAULT now();
        ALTER TABLE replay_session ADD COLUMN created_by text;
        ALTER TABLE replay_session ADD COLUMN parent_session_id uuid REFERENCES replay_session(id);
        CREATE INDEX idx_replay_due ON replay_session(state,next_tick_at);
        CREATE TABLE alert_action (
            id uuid PRIMARY KEY,
            alert_id uuid NOT NULL REFERENCES alert(id),
            actor_name text NOT NULL,
            action text NOT NULL,
            rationale text NOT NULL,
            before_lifecycle text NOT NULL,
            after_lifecycle text NOT NULL,
            recorded_at timestamptz NOT NULL DEFAULT now()
        );
    """)


def downgrade():
    raise RuntimeError("Replay and alert audit history must be retained")
