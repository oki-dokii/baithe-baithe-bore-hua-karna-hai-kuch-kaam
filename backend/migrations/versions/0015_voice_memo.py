"""Consent-scoped audio documents and untrusted transcript provenance.

Revision ID: 0015_voice_memo
Revises: 0014_alert_budget
"""

from alembic import op

revision = "0015_voice_memo"
down_revision = "0014_alert_budget"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE source_document ADD COLUMN doc_type text NOT NULL DEFAULT 'report'
            CHECK (doc_type IN ('report','voice_memo'));
        ALTER TABLE extracted_passage ADD COLUMN transcription_confidence numeric
            CHECK (transcription_confidence BETWEEN 0 AND 1);
        ALTER TABLE extracted_passage ADD COLUMN transcription_confidence_kind text
            CHECK (transcription_confidence_kind IN ('uncalibrated_token_likelihood'));
        ALTER TABLE extracted_passage ADD COLUMN transcription_language text
            CHECK (transcription_language IN ('as','hi','en'));
        ALTER TABLE extracted_passage ADD CONSTRAINT transcript_confidence_kind_pair CHECK
            ((transcription_confidence IS NULL) = (transcription_confidence_kind IS NULL));
        CREATE TABLE voice_memo (
            document_id uuid PRIMARY KEY REFERENCES source_document(id) ON DELETE RESTRICT,
            language text NOT NULL CHECK (language IN ('as','hi','en')),
            transcription_mode text NOT NULL CHECK (transcription_mode IN ('typed','local_asr')),
            typed_transcript text,
            consent_at timestamptz NOT NULL,
            audio_retention_until timestamptz NOT NULL,
            audio_purged_at timestamptz,
            CHECK ((transcription_mode='typed' AND length(btrim(typed_transcript)) > 0)
               OR (transcription_mode='local_asr' AND typed_transcript IS NULL))
        );
    """)


def downgrade() -> None:
    raise RuntimeError("Voice-memo consent and transcript provenance are retained; restore a backup")
