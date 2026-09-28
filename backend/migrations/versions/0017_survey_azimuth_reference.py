"""Require explicit, reviewed azimuth reference before deriving survey positions.

Revision ID: 0017_survey_azimuth_reference
Revises: 0016_pressure_window_evidence
"""

from alembic import op

revision = "0017_survey_azimuth_reference"
down_revision = "0016_pressure_window_evidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE wellbore ADD COLUMN azimuth_reference text
            CHECK (azimuth_reference IN ('true','grid','magnetic'));
        ALTER TABLE wellbore ADD COLUMN survey_reference_review_state text NOT NULL
            DEFAULT 'unreviewed'
            CHECK (survey_reference_review_state IN ('unreviewed','approved'));
        ALTER TABLE wellbore ADD COLUMN survey_reference_version integer
            CHECK (survey_reference_version > 0);
        ALTER TABLE wellbore ADD COLUMN survey_reference_reviewed_by text;
        ALTER TABLE wellbore ADD COLUMN survey_reference_review_reference text;
        ALTER TABLE wellbore ADD CONSTRAINT survey_reference_approval_requires_azimuth
            CHECK (survey_reference_review_state <> 'approved' OR (
                azimuth_reference IS NOT NULL AND survey_reference_version IS NOT NULL
                AND length(btrim(coalesce(survey_reference_reviewed_by,''))) > 0
                AND length(btrim(coalesce(survey_reference_review_reference,''))) > 0));
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE wellbore DROP CONSTRAINT survey_reference_approval_requires_azimuth;
        ALTER TABLE wellbore DROP COLUMN survey_reference_review_reference;
        ALTER TABLE wellbore DROP COLUMN survey_reference_reviewed_by;
        ALTER TABLE wellbore DROP COLUMN survey_reference_version;
        ALTER TABLE wellbore DROP COLUMN survey_reference_review_state;
        ALTER TABLE wellbore DROP COLUMN azimuth_reference;
    """)
