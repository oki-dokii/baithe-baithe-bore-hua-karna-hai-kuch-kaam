"""Fail-closed dataset provenance and prospective decision-chain integrity.

Revision ID: 0007_provenance_decision_ledger
Revises: 0006_event_onset_bounds
"""

from alembic import op

revision = "0007_provenance_decision_ledger"
down_revision = "0006_event_onset_bounds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE dataset
            ADD COLUMN origin_kind text NOT NULL DEFAULT 'unclassified',
            ADD COLUMN authorization_state text NOT NULL DEFAULT 'unverified',
            ADD COLUMN applicability text NOT NULL DEFAULT 'review_only';
        UPDATE dataset SET origin_kind='synthetic', authorization_state='synthetic',
            applicability='demo_only' WHERE kind='synthetic';
        UPDATE dataset SET origin_kind='public_primary' WHERE kind='public';
        ALTER TABLE dataset
            ADD CONSTRAINT dataset_origin_kind CHECK (origin_kind IN
                ('unclassified','operator_record','public_primary','regional_context','synthetic','derived')),
            ADD CONSTRAINT dataset_authorization_state CHECK (authorization_state IN
                ('unverified','public_permitted','restricted_authorized','synthetic')),
            ADD CONSTRAINT dataset_applicability CHECK (applicability IN
                ('review_only','direct_offset','analog_only','regional_only','demo_only')),
            ADD CONSTRAINT dataset_provenance_consistency CHECK (
                (kind <> 'synthetic' OR (origin_kind='synthetic' AND
                    authorization_state='synthetic' AND applicability='demo_only'))
                AND (origin_kind <> 'synthetic' OR kind='synthetic')
                AND (origin_kind <> 'regional_context' OR applicability='regional_only')
                AND (origin_kind <> 'unclassified' OR applicability='review_only')
                AND (applicability NOT IN ('direct_offset','analog_only') OR
                    (origin_kind IN ('operator_record','public_primary')
                     AND authorization_state IN ('public_permitted','restricted_authorized')
                     AND qualification_status='qualified'))
            );

        CREATE FUNCTION nwis_check_event_provenance() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE source dataset%ROWTYPE;
        BEGIN
            IF NEW.review_state <> 'approved' THEN RETURN NEW; END IF;
            SELECT d.* INTO source FROM wellbore b JOIN well w ON w.id=b.well_id
                JOIN dataset d ON d.id=w.dataset_id WHERE b.id=NEW.wellbore_id;
            IF source.id IS NULL THEN
                RAISE EXCEPTION 'Event source dataset missing' USING ERRCODE='23514';
            END IF;
            IF NOT ((source.kind='synthetic' AND source.origin_kind='synthetic'
                         AND source.applicability='demo_only')
                    OR (source.kind<>'synthetic' AND source.qualification_status='qualified'
                         AND source.applicability IN ('direct_offset','analog_only')
                         AND source.authorization_state IN ('public_permitted','restricted_authorized')))
            THEN
                RAISE EXCEPTION 'Unqualified source cannot create approved event'
                    USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER check_event_provenance BEFORE INSERT OR UPDATE OF review_state,wellbore_id
            ON drilling_event FOR EACH ROW EXECUTE FUNCTION nwis_check_event_provenance();

        CREATE FUNCTION nwis_check_event_passage_dataset() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE event_dataset uuid; passage_dataset uuid;
        BEGIN
            SELECT w.dataset_id INTO event_dataset FROM drilling_event e
                JOIN wellbore b ON b.id=e.wellbore_id JOIN well w ON w.id=b.well_id
                WHERE e.id=NEW.event_id;
            SELECT d.dataset_id INTO passage_dataset FROM extracted_passage p
                JOIN source_document d ON d.id=p.document_id WHERE p.id=NEW.passage_id;
            IF event_dataset IS DISTINCT FROM passage_dataset THEN
                RAISE EXCEPTION 'Event and cited passage belong to different datasets'
                    USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER check_event_passage_dataset BEFORE INSERT OR UPDATE OF event_id,passage_id
            ON event_passage FOR EACH ROW EXECUTE FUNCTION nwis_check_event_passage_dataset();

        CREATE TABLE decision_chain_state (
            singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
            last_sequence bigint NOT NULL DEFAULT 0 CHECK (last_sequence >= 0),
            last_hash text NOT NULL DEFAULT repeat('0',64) CHECK (last_hash ~ '^[0-9a-f]{64}$')
        );
        INSERT INTO decision_chain_state(singleton) VALUES(true);
        CREATE TABLE decision_ledger (
            sequence bigint PRIMARY KEY CHECK (sequence > 0),
            recorded_at timestamptz NOT NULL,
            actor_name text NOT NULL,
            action text NOT NULL,
            entity_type text NOT NULL,
            entity_id uuid NOT NULL,
            payload jsonb NOT NULL,
            previous_hash text NOT NULL CHECK (previous_hash ~ '^[0-9a-f]{64}$'),
            entry_hash text NOT NULL CHECK (entry_hash ~ '^[0-9a-f]{64}$')
        );
        CREATE INDEX idx_decision_ledger_entity ON decision_ledger(entity_type,entity_id,sequence);
        CREATE FUNCTION nwis_reject_decision_ledger_change() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Decision ledger is append-only' USING ERRCODE='23514';
        END $$;
        CREATE TRIGGER immutable_decision_ledger BEFORE UPDATE OR DELETE ON decision_ledger
            FOR EACH ROW EXECUTE FUNCTION nwis_reject_decision_ledger_change();
        CREATE TRIGGER immutable_decision_ledger_truncate BEFORE TRUNCATE ON decision_ledger
            FOR EACH STATEMENT EXECUTE FUNCTION nwis_reject_decision_ledger_change();
    """)


def downgrade() -> None:
    raise RuntimeError("Provenance and decision history must be retained; restore a backup")
