"""Document jobs, staged evidence, optimistic review and request idempotency."""

from alembic import op

revision = "0003_document_ingestion"
down_revision = "0002_local_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE source_document ADD COLUMN uploaded_by text;
        ALTER TABLE source_document ADD COLUMN review_version integer NOT NULL DEFAULT 1;
        ALTER TABLE source_document ADD COLUMN extraction_generation integer NOT NULL DEFAULT 1;
        ALTER TABLE ingestion_job ADD COLUMN claim_token uuid;
        ALTER TABLE ingestion_job ADD COLUMN run_id uuid;
        ALTER TABLE ingestion_job ADD COLUMN generation integer NOT NULL DEFAULT 1;
        ALTER TABLE ingestion_job ADD COLUMN next_attempt_at timestamptz NOT NULL DEFAULT now();
        ALTER TABLE ingestion_job ADD COLUMN error_message text;
        ALTER TABLE ingestion_job ADD COLUMN pages_done integer NOT NULL DEFAULT 0;
        CREATE UNIQUE INDEX idx_document_active_job ON ingestion_job(document_id)
            WHERE status IN ('pending','processing','retrying');
        CREATE INDEX idx_ingestion_claim ON ingestion_job(status, next_attempt_at);
        ALTER TABLE extraction_run ADD COLUMN provider text;
        ALTER TABLE extraction_run ADD COLUMN model_id text;
        ALTER TABLE extraction_run ADD COLUMN prompt_version text;
        ALTER TABLE extraction_run ADD COLUMN error_code text;
        ALTER TABLE extracted_passage ADD COLUMN preview_key text;
        ALTER TABLE extracted_passage ADD COLUMN word_boxes jsonb NOT NULL DEFAULT '[]';
        ALTER TABLE extracted_passage ADD COLUMN extraction_run_id uuid REFERENCES extraction_run(id);
        CREATE TABLE document_event_draft (
            id uuid PRIMARY KEY,
            document_id uuid NOT NULL REFERENCES source_document(id),
            run_id uuid REFERENCES extraction_run(id),
            passage_id uuid NOT NULL REFERENCES extracted_passage(id),
            original_fields jsonb NOT NULL,
            current_fields jsonb NOT NULL,
            normalized_fields jsonb NOT NULL,
            issues jsonb NOT NULL DEFAULT '[]',
            state text NOT NULL DEFAULT 'needs_review'
                CHECK (state IN ('needs_review','approved','rejected')),
            version integer NOT NULL DEFAULT 1 CHECK (version > 0),
            canonical_event_id uuid REFERENCES drilling_event(id),
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_document_drafts ON document_event_draft(document_id, state);
        ALTER TABLE drilling_event ADD COLUMN source_depth_axis text;
        ALTER TABLE drilling_event ADD COLUMN source_depth_unit text;
        ALTER TABLE drilling_event ADD COLUMN source_datum text;
        ALTER TABLE drilling_event ADD COLUMN source_fields jsonb NOT NULL DEFAULT '{}';
        ALTER TABLE drilling_event ADD COLUMN quality_issues jsonb NOT NULL DEFAULT '[]';
        ALTER TABLE review_decision ADD COLUMN before_value jsonb;
        ALTER TABLE review_decision ADD COLUMN after_value jsonb;
        ALTER TABLE review_decision ADD COLUMN document_id uuid REFERENCES source_document(id);
        CREATE TABLE request_receipt (
            actor_name text NOT NULL,
            idempotency_key text NOT NULL,
            request_hash text NOT NULL,
            response jsonb NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (actor_name, idempotency_key)
        );
        CREATE TABLE service_heartbeat (
            service text PRIMARY KEY,
            last_seen_at timestamptz NOT NULL DEFAULT now(),
            details jsonb NOT NULL DEFAULT '{}'
        );
    """)


def downgrade() -> None:
    raise RuntimeError("Evidence history is retained; restore a backup to reverse this migration")
