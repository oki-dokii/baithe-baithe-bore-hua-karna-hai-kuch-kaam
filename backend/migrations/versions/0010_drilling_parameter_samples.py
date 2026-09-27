"""Historical drilling-parameter provenance, separate from replay telemetry.

Revision ID: 0010_drilling_parameter_samples
Revises: 0009_report_fact_questions
"""

from alembic import op

revision = "0010_drilling_parameter_samples"
down_revision = "0009_report_fact_questions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE drilling_parameter_source (
            id uuid PRIMARY KEY,
            dataset_id uuid NOT NULL REFERENCES dataset(id) ON DELETE RESTRICT,
            external_id text NOT NULL CHECK (length(external_id) BETWEEN 1 AND 240),
            source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
            source_kind text NOT NULL CHECK (source_kind IN ('witsml_export','csv_export','other')),
            source_reference text NOT NULL CHECK (length(source_reference) > 0),
            permission_reference text NOT NULL CHECK (length(permission_reference) > 0),
            source_timezone text NOT NULL CHECK (length(source_timezone) > 0),
            md_datum text NOT NULL CHECK (length(md_datum) > 0),
            source_units jsonb NOT NULL CHECK (jsonb_typeof(source_units) = 'object'),
            mapping_version text NOT NULL CHECK (length(mapping_version) > 0),
            units_reviewed boolean NOT NULL DEFAULT false,
            timezone_reviewed boolean NOT NULL DEFAULT false,
            datum_reviewed boolean NOT NULL DEFAULT false,
            qualification_state text NOT NULL DEFAULT 'staged'
                CHECK (qualification_state IN ('staged','qualified','rejected')),
            qualified_by text,
            qualified_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (dataset_id, external_id),
            UNIQUE (dataset_id, source_sha256),
            CHECK ((qualification_state='qualified') =
                (qualified_by IS NOT NULL AND qualified_at IS NOT NULL))
        );
        CREATE TABLE drilling_parameter_sample (
            id uuid PRIMARY KEY,
            source_id uuid NOT NULL REFERENCES drilling_parameter_source(id) ON DELETE RESTRICT,
            wellbore_id uuid NOT NULL REFERENCES wellbore(id) ON DELETE RESTRICT,
            source_record_id text NOT NULL CHECK (length(source_record_id) BETWEEN 1 AND 240),
            revision integer NOT NULL CHECK (revision > 0),
            operation text NOT NULL CHECK (operation IN ('upsert','delete')),
            observed_at timestamptz NOT NULL,
            available_at timestamptz NOT NULL,
            received_at timestamptz NOT NULL,
            md_m numeric CHECK (md_m >= 0),
            tvd_m numeric CHECK (tvd_m >= 0),
            depth_reference_id uuid REFERENCES depth_reference(id) ON DELETE RESTRICT,
            rig_state text NOT NULL CHECK (rig_state IN
                ('forward_drilling','circulating','tripping','other','unknown')),
            quality text NOT NULL CHECK (quality IN ('good','suspect','bad','missing')),
            source_quality_code text,
            rop_m_per_h numeric CHECK (rop_m_per_h >= 0),
            wob_kn numeric CHECK (wob_kn >= 0),
            rpm numeric CHECK (rpm >= 0),
            torque_kn_m numeric CHECK (torque_kn_m >= 0),
            flow_in_l_per_min numeric CHECK (flow_in_l_per_min >= 0),
            mud_density_kg_per_m3 numeric CHECK (mud_density_kg_per_m3 > 0),
            raw_values jsonb NOT NULL DEFAULT '{}'::jsonb
                CHECK (jsonb_typeof(raw_values) = 'object'),
            row_sha256 text NOT NULL CHECK (row_sha256 ~ '^[0-9a-f]{64}$'),
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (source_id, source_record_id, revision),
            CHECK (observed_at <= available_at AND available_at <= received_at),
            CHECK ((operation='upsert' AND md_m IS NOT NULL)
                OR (operation='delete' AND quality='missing'
                    AND rop_m_per_h IS NULL AND wob_kn IS NULL AND rpm IS NULL
                    AND torque_kn_m IS NULL AND flow_in_l_per_min IS NULL
                    AND mud_density_kg_per_m3 IS NULL))
        );
        CREATE INDEX idx_drilling_parameter_bore_time
            ON drilling_parameter_sample(wellbore_id, observed_at);
        CREATE INDEX idx_drilling_parameter_source_record
            ON drilling_parameter_sample(source_id, source_record_id, revision DESC);

        CREATE FUNCTION nwis_check_drilling_parameter_source() RETURNS trigger LANGUAGE plpgsql AS $$
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
                    NEW.md_datum,NEW.source_units,NEW.mapping_version)
                    IS DISTINCT FROM
                   (OLD.dataset_id,OLD.external_id,OLD.source_sha256,OLD.source_kind,
                    OLD.source_reference,OLD.permission_reference,OLD.source_timezone,
                    OLD.md_datum,OLD.source_units,OLD.mapping_version) THEN
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
                    AND NEW.source_units <> '{}'::jsonb)
                THEN
                    RAISE EXCEPTION 'Unqualified dataset or source mapping'
                        USING ERRCODE='23514';
                END IF;
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER check_drilling_parameter_source
            BEFORE INSERT OR UPDATE ON drilling_parameter_source
            FOR EACH ROW EXECUTE FUNCTION nwis_check_drilling_parameter_source();

        CREATE FUNCTION nwis_check_drilling_parameter_sample() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE source_row drilling_parameter_source%ROWTYPE;
                bore_dataset uuid;
                previous_revision drilling_parameter_sample%ROWTYPE;
        BEGIN
            SELECT * INTO source_row FROM drilling_parameter_source WHERE id=NEW.source_id FOR SHARE;
            SELECT w.dataset_id INTO bore_dataset FROM wellbore b JOIN well w ON w.id=b.well_id
                WHERE b.id=NEW.wellbore_id;
            IF bore_dataset IS DISTINCT FROM source_row.dataset_id THEN
                RAISE EXCEPTION 'Historical sample and wellbore dataset mismatch'
                    USING ERRCODE='23514';
            END IF;
            IF source_row.qualification_state <> 'staged' THEN
                RAISE EXCEPTION 'Only staged sources accept new samples' USING ERRCODE='23514';
            END IF;
            SELECT * INTO previous_revision FROM drilling_parameter_sample
                WHERE source_id=NEW.source_id AND source_record_id=NEW.source_record_id
                ORDER BY revision DESC LIMIT 1;
            IF (NEW.revision=1 AND previous_revision.id IS NOT NULL)
                OR (NEW.revision>1 AND (previous_revision.id IS NULL
                    OR NEW.revision<>previous_revision.revision+1
                    OR NEW.wellbore_id<>previous_revision.wellbore_id))
                OR (NEW.operation='delete' AND NEW.revision=1) THEN
                RAISE EXCEPTION 'Invalid historical sample correction chain'
                    USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER check_drilling_parameter_sample
            BEFORE INSERT ON drilling_parameter_sample
            FOR EACH ROW EXECUTE FUNCTION nwis_check_drilling_parameter_sample();
        CREATE FUNCTION nwis_reject_historical_sample_change() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Historical samples are append-only' USING ERRCODE='23514';
        END $$;
        CREATE TRIGGER immutable_drilling_parameter_sample
            BEFORE UPDATE OR DELETE ON drilling_parameter_sample
            FOR EACH ROW EXECUTE FUNCTION nwis_reject_historical_sample_change();
        CREATE TRIGGER immutable_drilling_parameter_sample_truncate
            BEFORE TRUNCATE ON drilling_parameter_sample
            FOR EACH STATEMENT EXECUTE FUNCTION nwis_reject_historical_sample_change();
    """)


def downgrade() -> None:
    raise RuntimeError("Historical data and correction lineage are retained; restore a backup")
