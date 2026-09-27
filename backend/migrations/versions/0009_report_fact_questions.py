"""Curated question mapping for reviewed report facts.

Revision ID: 0009_report_fact_questions
Revises: 0008_reviewed_report_facts
"""

from alembic import op

revision = "0009_report_fact_questions"
down_revision = "0008_reviewed_report_facts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE reviewed_report_fact ADD COLUMN review_rationale text,
            ADD COLUMN ocr_image_verified boolean NOT NULL DEFAULT false;
        CREATE TABLE report_fact_question (
            id uuid PRIMARY KEY,
            dataset_id uuid NOT NULL REFERENCES dataset(id),
            fact_key text NOT NULL CHECK (length(fact_key) BETWEEN 3 AND 120),
            question text NOT NULL CHECK (length(question) BETWEEN 5 AND 500),
            state text NOT NULL CHECK (state IN ('ready','conflict_blocked')),
            reason text CHECK (reason IS NULL OR length(reason) BETWEEN 3 AND 1000),
            reviewer_name text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (dataset_id, fact_key, question),
            CHECK (state <> 'conflict_blocked' OR reason IS NOT NULL)
        );
        CREATE INDEX idx_report_fact_question_dataset ON report_fact_question(dataset_id, created_at);
    """)


def downgrade() -> None:
    raise RuntimeError(
        "Question review history is retained; restore a backup to reverse this migration"
    )
