"""Preserve reviewer-adjudicated onset uncertainty separately from event depth.

Revision ID: 0006_event_onset_bounds
Revises: 0005_event_semantic
"""

from alembic import op

revision = "0006_event_onset_bounds"
down_revision = "0005_event_semantic"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE drilling_event
            ADD COLUMN onset_time_earliest timestamptz,
            ADD COLUMN onset_time_latest timestamptz,
            ADD COLUMN onset_time_basis text NOT NULL DEFAULT 'unspecified'
                CHECK (onset_time_basis IN ('exact_timelog','day_only_ddr','shift_report','unspecified')),
            ADD CONSTRAINT event_onset_bounds CHECK (
                (onset_time_basis = 'unspecified' AND onset_time_earliest IS NULL
                    AND onset_time_latest IS NULL)
                OR (onset_time_basis <> 'unspecified' AND onset_time_earliest IS NOT NULL
                    AND onset_time_latest IS NOT NULL
                    AND onset_time_earliest <= onset_time_latest
                    AND (onset_time_basis <> 'exact_timelog'
                        OR onset_time_earliest = onset_time_latest))
            );
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE drilling_event DROP CONSTRAINT event_onset_bounds;
        ALTER TABLE drilling_event DROP COLUMN onset_time_basis;
        ALTER TABLE drilling_event DROP COLUMN onset_time_latest;
        ALTER TABLE drilling_event DROP COLUMN onset_time_earliest;
    """)
