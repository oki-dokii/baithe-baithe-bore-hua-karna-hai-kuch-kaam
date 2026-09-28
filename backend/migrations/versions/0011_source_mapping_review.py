"""Persist historical mapping evidence and require rig-state review.

Revision ID: 0011_source_mapping_review
Revises: 0010_drilling_parameter_samples
"""

from alembic import op

revision = "0011_source_mapping_review"
down_revision = "0010_drilling_parameter_samples"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE drilling_parameter_source
            ADD COLUMN mapping_evidence jsonb NOT NULL DEFAULT '{}'::jsonb
                CHECK (jsonb_typeof(mapping_evidence)='object'),
            ADD COLUMN rig_state_reviewed boolean NOT NULL DEFAULT false;

        CREATE OR REPLACE FUNCTION nwis_check_drilling_parameter_source()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE source_dataset dataset%ROWTYPE;
        BEGIN
            SELECT * INTO source_dataset FROM dataset WHERE id=NEW.dataset_id;
            IF source_dataset.kind='synthetic' THEN
                RAISE EXCEPTION 'Historical source cannot belong to synthetic dataset'
                    USING ERRCODE='23514';
            END IF;
            IF TG_OP='INSERT' THEN
                IF NEW.qualification_state <> 'staged' THEN
                    RAISE EXCEPTION 'Historical source must start staged' USING ERRCODE='23514';
                END IF;
            ELSE
                IF (NEW.dataset_id,NEW.external_id,NEW.source_sha256,NEW.source_kind,
                    NEW.source_reference,NEW.permission_reference,NEW.source_timezone,
                    NEW.md_datum,NEW.source_units,NEW.mapping_version,NEW.mapping_evidence)
                    IS DISTINCT FROM
                   (OLD.dataset_id,OLD.external_id,OLD.source_sha256,OLD.source_kind,
                    OLD.source_reference,OLD.permission_reference,OLD.source_timezone,
                    OLD.md_datum,OLD.source_units,OLD.mapping_version,OLD.mapping_evidence) THEN
                    RAISE EXCEPTION 'Historical source identity and mapping are immutable'
                        USING ERRCODE='23514';
                END IF;
            END IF;
            IF NEW.qualification_state='qualified' THEN
                IF NOT (source_dataset.qualification_status='qualified'
                    AND source_dataset.origin_kind IN ('operator_record','public_primary')
                    AND source_dataset.authorization_state IN
                        ('public_permitted','restricted_authorized')
                    AND source_dataset.applicability IN ('direct_offset','analog_only')
                    AND NEW.units_reviewed AND NEW.timezone_reviewed AND NEW.datum_reviewed
                    AND NEW.rig_state_reviewed
                    AND NEW.source_units <> '{}'::jsonb
                    AND NEW.mapping_evidence ?& ARRAY[
                        'unit_reference','depth_semantics_reference',
                        'availability_reference','availability_policy',
                        'rig_state_basis','selection_start_at','selection_end_at',
                        'receipt_at']
                    AND NOT EXISTS (
                        SELECT 1 FROM jsonb_each_text(NEW.mapping_evidence) AS evidence(key,value)
                        WHERE evidence.value IS NULL OR btrim(evidence.value)=''
                    )) THEN
                    RAISE EXCEPTION 'Unqualified dataset or source mapping'
                        USING ERRCODE='23514';
                END IF;
            END IF;
            RETURN NEW;
        END $$;
    """)


def downgrade() -> None:
    raise RuntimeError("Historical mapping and review lineage are retained; restore a backup")
