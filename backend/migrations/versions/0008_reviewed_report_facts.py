"""Separate, reviewer-approved report facts from event and raw-page retrieval.

Revision ID: 0008_reviewed_report_facts
Revises: 0007_provenance_decision_ledger
"""

from alembic import op

revision = "0008_reviewed_report_facts"
down_revision = "0007_provenance_decision_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE reviewed_report_fact (
            id uuid PRIMARY KEY,
            dataset_id uuid NOT NULL REFERENCES dataset(id),
            passage_id uuid NOT NULL REFERENCES extracted_passage(id),
            fact_key text NOT NULL CHECK (length(fact_key) BETWEEN 3 AND 120),
            answer text NOT NULL CHECK (length(answer) BETWEEN 1 AND 1000),
            quote text NOT NULL CHECK (length(quote) BETWEEN 1 AND 4000),
            reviewer_name text NOT NULL,
            reviewed_at timestamptz NOT NULL DEFAULT now(),
            state text NOT NULL DEFAULT 'approved' CHECK (state IN ('approved','withdrawn')),
            UNIQUE (passage_id, fact_key, answer, quote)
        );
        CREATE INDEX idx_reviewed_fact_lookup ON reviewed_report_fact(dataset_id, fact_key)
            WHERE state='approved';
        CREATE FUNCTION nwis_check_report_fact() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE source dataset%ROWTYPE; passage_dataset uuid;
        BEGIN
            SELECT d.* INTO source FROM dataset d WHERE d.id=NEW.dataset_id;
            SELECT sd.dataset_id INTO passage_dataset FROM extracted_passage p
                JOIN source_document sd ON sd.id=p.document_id WHERE p.id=NEW.passage_id;
            IF passage_dataset IS DISTINCT FROM NEW.dataset_id THEN
                RAISE EXCEPTION 'Fact and passage belong to different datasets' USING ERRCODE='23514';
            END IF;
            IF NEW.state='approved' AND NOT (
                (source.kind='synthetic' AND source.origin_kind='synthetic'
                    AND source.applicability='demo_only')
                OR (source.kind<>'synthetic' AND source.qualification_status='qualified'
                    AND source.origin_kind IN ('operator_record','public_primary')
                    AND source.authorization_state IN ('public_permitted','restricted_authorized')
                    AND source.applicability IN ('direct_offset','analog_only'))
            ) THEN
                RAISE EXCEPTION 'Unqualified source cannot create approved report fact'
                    USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER check_report_fact BEFORE INSERT OR UPDATE OF state,dataset_id,passage_id
            ON reviewed_report_fact FOR EACH ROW EXECUTE FUNCTION nwis_check_report_fact();
    """)


def downgrade() -> None:
    raise RuntimeError(
        "Reviewed evidence history is retained; restore a backup to reverse this migration"
    )
