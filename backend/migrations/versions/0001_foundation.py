"""Initial NWIS foundation schema.

Revision ID: 0001_foundation
Revises:
"""

from alembic import op

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("""
        CREATE TABLE dataset (
            id uuid PRIMARY KEY,
            external_id text NOT NULL UNIQUE,
            name text NOT NULL,
            kind text NOT NULL CHECK (kind IN ('synthetic','public','private')),
            source_url text,
            version text NOT NULL,
            license_reference text,
            qualification_status text NOT NULL DEFAULT 'unqualified',
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE depth_reference (
            id uuid PRIMARY KEY,
            kind text NOT NULL,
            elevation_above_msl_m numeric,
            review_state text NOT NULL DEFAULT 'draft',
            CHECK (review_state IN ('draft','needs_review','approved','rejected','superseded'))
        );
        CREATE TABLE well (
            id uuid PRIMARY KEY,
            dataset_id uuid NOT NULL REFERENCES dataset(id) ON DELETE RESTRICT,
            external_id text NOT NULL,
            name text NOT NULL,
            basin_name text,
            field_name text,
            status text NOT NULL DEFAULT 'historical',
            surface_point geography(Point,4326) NOT NULL,
            depth_reference_id uuid REFERENCES depth_reference(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (dataset_id, external_id)
        );
        CREATE INDEX idx_well_surface ON well USING gist (surface_point);
        CREATE TABLE wellbore (
            id uuid PRIMARY KEY,
            well_id uuid NOT NULL REFERENCES well(id) ON DELETE RESTRICT,
            external_id text NOT NULL,
            parent_wellbore_id uuid REFERENCES wellbore(id),
            status text NOT NULL DEFAULT 'historical',
            UNIQUE (well_id, external_id)
        );
        CREATE TABLE trajectory_station (
            id uuid PRIMARY KEY,
            wellbore_id uuid NOT NULL REFERENCES wellbore(id) ON DELETE RESTRICT,
            survey_version integer NOT NULL CHECK (survey_version > 0),
            md_m numeric NOT NULL CHECK (md_m >= 0),
            tvd_m numeric NOT NULL CHECK (tvd_m >= 0),
            inclination_deg numeric CHECK (inclination_deg BETWEEN 0 AND 180),
            azimuth_deg numeric CHECK (azimuth_deg >= 0 AND azimuth_deg < 360),
            point geography(Point,4326),
            UNIQUE (wellbore_id, survey_version, md_m)
        );
        CREATE INDEX idx_trajectory_wellbore_md ON trajectory_station(wellbore_id, md_m);
        CREATE TABLE formation (
            id uuid PRIMARY KEY,
            basin_name text NOT NULL,
            canonical_code text NOT NULL,
            display_name text NOT NULL,
            UNIQUE (basin_name, canonical_code)
        );
        CREATE TABLE formation_alias (
            id uuid PRIMARY KEY,
            formation_id uuid NOT NULL REFERENCES formation(id),
            dataset_id uuid NOT NULL REFERENCES dataset(id),
            alias text NOT NULL,
            review_state text NOT NULL DEFAULT 'draft',
            UNIQUE (dataset_id, alias)
        );
        CREATE TABLE formation_interval (
            id uuid PRIMARY KEY,
            wellbore_id uuid NOT NULL REFERENCES wellbore(id),
            formation_id uuid NOT NULL REFERENCES formation(id),
            occurrence_key text NOT NULL DEFAULT '1',
            top_md_m numeric NOT NULL CHECK (top_md_m >= 0),
            base_md_m numeric CHECK (base_md_m > top_md_m),
            top_tvd_m numeric,
            base_tvd_m numeric,
            depth_reference_id uuid NOT NULL REFERENCES depth_reference(id),
            review_state text NOT NULL DEFAULT 'draft',
            version integer NOT NULL DEFAULT 1 CHECK (version > 0),
            CHECK (base_tvd_m IS NULL OR (top_tvd_m IS NOT NULL AND base_tvd_m > top_tvd_m)),
            UNIQUE (wellbore_id, formation_id, occurrence_key, version)
        );
        CREATE INDEX idx_formation_interval_wellbore ON formation_interval(wellbore_id, top_md_m);
        CREATE TABLE drilling_run (
            id uuid PRIMARY KEY,
            wellbore_id uuid NOT NULL REFERENCES wellbore(id),
            run_number text NOT NULL,
            start_md_m numeric CHECK (start_md_m >= 0),
            end_md_m numeric CHECK (end_md_m >= start_md_m),
            bit_type text,
            bha_description text,
            UNIQUE (wellbore_id, run_number)
        );
        CREATE TABLE reservoir_property (
            id uuid PRIMARY KEY,
            formation_interval_id uuid NOT NULL REFERENCES formation_interval(id),
            property_type text NOT NULL,
            value numeric,
            unit text NOT NULL,
            top_md_m numeric,
            base_md_m numeric,
            CHECK (base_md_m IS NULL OR base_md_m >= top_md_m)
        );
        CREATE TABLE mud_program (
            id uuid PRIMARY KEY,
            wellbore_id uuid NOT NULL REFERENCES wellbore(id),
            interval_top_md_m numeric CHECK (interval_top_md_m >= 0),
            interval_base_md_m numeric CHECK (interval_base_md_m >= interval_top_md_m),
            mud_type text,
            mud_density_kg_m3 numeric CHECK (mud_density_kg_m3 > 0),
            rheology_notes text
        );
        CREATE TABLE casing_program (
            id uuid PRIMARY KEY,
            wellbore_id uuid NOT NULL REFERENCES wellbore(id),
            hole_diameter_m numeric CHECK (hole_diameter_m > 0),
            casing_diameter_m numeric CHECK (casing_diameter_m > 0),
            setting_depth_md_m numeric CHECK (setting_depth_md_m >= 0),
            casing_type text
        );
        CREATE TABLE cementing_operation (
            id uuid PRIMARY KEY,
            casing_id uuid NOT NULL REFERENCES casing_program(id),
            cement_volume_m3 numeric CHECK (cement_volume_m3 >= 0),
            cement_type text,
            recorded_outcome text,
            notes text
        );
        CREATE TABLE source_document (
            id uuid PRIMARY KEY,
            dataset_id uuid NOT NULL REFERENCES dataset(id),
            external_id text NOT NULL,
            storage_key text,
            sha256 text CHECK (sha256 IS NULL OR sha256 ~ '^[0-9a-f]{64}$'),
            filename text NOT NULL,
            mime_type text NOT NULL,
            byte_size bigint CHECK (byte_size >= 0),
            page_count integer CHECK (page_count > 0),
            version integer NOT NULL DEFAULT 1 CHECK (version > 0),
            ingest_status text NOT NULL DEFAULT 'pending',
            access_class text NOT NULL DEFAULT 'demo',
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (dataset_id, external_id, version),
            UNIQUE (dataset_id, sha256)
        );
        CREATE TABLE document_wellbore (
            document_id uuid NOT NULL REFERENCES source_document(id) ON DELETE RESTRICT,
            wellbore_id uuid NOT NULL REFERENCES wellbore(id) ON DELETE RESTRICT,
            PRIMARY KEY (document_id, wellbore_id)
        );
        CREATE TABLE ingestion_job (
            id uuid PRIMARY KEY,
            document_id uuid NOT NULL REFERENCES source_document(id),
            stage text NOT NULL,
            status text NOT NULL DEFAULT 'pending',
            attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
            leased_until timestamptz,
            error_code text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE extraction_run (
            id uuid PRIMARY KEY,
            document_id uuid NOT NULL REFERENCES source_document(id),
            extractor_version text NOT NULL,
            schema_version text NOT NULL,
            status text NOT NULL,
            started_at timestamptz NOT NULL DEFAULT now(),
            finished_at timestamptz
        );
        CREATE TABLE extracted_passage (
            id uuid PRIMARY KEY,
            document_id uuid NOT NULL REFERENCES source_document(id),
            page_number integer NOT NULL CHECK (page_number > 0),
            section_label text,
            raw_text text NOT NULL,
            ocr_applied boolean NOT NULL DEFAULT false,
            ocr_confidence numeric CHECK (ocr_confidence BETWEEN 0 AND 1),
            text_version integer NOT NULL DEFAULT 1 CHECK (text_version > 0),
            UNIQUE (document_id, page_number, text_version)
        );
        CREATE INDEX idx_passage_fts ON extracted_passage USING gin (to_tsvector('english', raw_text));
        CREATE TABLE passage_embedding (
            id uuid PRIMARY KEY,
            passage_id uuid NOT NULL REFERENCES extracted_passage(id),
            model_id text NOT NULL,
            text_version integer NOT NULL CHECK (text_version > 0),
            dimension integer NOT NULL CHECK (dimension > 0),
            embedding vector NOT NULL,
            CHECK (vector_dims(embedding) = dimension),
            UNIQUE (passage_id, model_id, text_version)
        );
        CREATE TABLE drilling_event (
            id uuid PRIMARY KEY,
            external_id text,
            wellbore_id uuid NOT NULL REFERENCES wellbore(id),
            formation_interval_id uuid REFERENCES formation_interval(id),
            event_type text NOT NULL CHECK (event_type IN (
                'mud_loss','kick','stuck_pipe','overpressure','torque_spike',
                'tight_hole','fishing','cementing_issue','other'
            )),
            start_md_m numeric CHECK (start_md_m >= 0),
            end_md_m numeric CHECK (end_md_m >= start_md_m),
            severity text CHECK (severity IN ('low','medium','high','critical')),
            mechanism text,
            description text,
            review_state text NOT NULL DEFAULT 'draft' CHECK (
                review_state IN ('draft','needs_review','approved','rejected','superseded')
            ),
            version integer NOT NULL DEFAULT 1 CHECK (version > 0),
            extraction_run_id uuid REFERENCES extraction_run(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (wellbore_id, external_id, version)
        );
        CREATE INDEX idx_event_wellbore_md ON drilling_event(wellbore_id, start_md_m);
        CREATE INDEX idx_event_type ON drilling_event(event_type, review_state);
        CREATE TABLE event_passage (
            event_id uuid NOT NULL REFERENCES drilling_event(id) ON DELETE RESTRICT,
            passage_id uuid NOT NULL REFERENCES extracted_passage(id) ON DELETE RESTRICT,
            support_kind text NOT NULL DEFAULT 'direct',
            PRIMARY KEY (event_id, passage_id)
        );
        CREATE TABLE mitigation (
            id uuid PRIMARY KEY,
            event_id uuid NOT NULL REFERENCES drilling_event(id),
            action_taken text NOT NULL,
            effectiveness text,
            CHECK (effectiveness IS NULL OR effectiveness IN ('successful','partial','unsuccessful','unknown'))
        );
        CREATE TABLE event_outcome (
            id uuid PRIMARY KEY,
            event_id uuid NOT NULL REFERENCES drilling_event(id),
            mitigation_id uuid REFERENCES mitigation(id),
            outcome text NOT NULL CHECK (outcome IN ('successful','partial','unsuccessful','unknown')),
            narrative text
        );
        CREATE TABLE npt_event (
            id uuid PRIMARY KEY,
            event_id uuid NOT NULL REFERENCES drilling_event(id),
            duration_h numeric NOT NULL CHECK (duration_h >= 0),
            duration_source text NOT NULL
        );
        CREATE TABLE fishing_operation (
            id uuid PRIMARY KEY,
            event_id uuid NOT NULL UNIQUE REFERENCES drilling_event(id),
            tool_left_in_hole text,
            fishing_tool_used text,
            attempts integer CHECK (attempts >= 0),
            duration_h numeric CHECK (duration_h >= 0),
            outcome text,
            fish_recovered_pct numeric CHECK (fish_recovered_pct BETWEEN 0 AND 100)
        );
        CREATE TABLE replay_session (
            id uuid PRIMARY KEY,
            active_wellbore_id uuid NOT NULL REFERENCES wellbore(id),
            scenario_id text NOT NULL,
            source_mode text NOT NULL DEFAULT 'SIMULATED',
            state text NOT NULL DEFAULT 'stopped',
            speed numeric NOT NULL DEFAULT 1 CHECK (speed > 0),
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE telemetry_sample (
            id uuid PRIMARY KEY,
            wellbore_id uuid NOT NULL REFERENCES wellbore(id),
            replay_session_id uuid REFERENCES replay_session(id),
            sequence bigint,
            observed_at timestamptz NOT NULL,
            received_at timestamptz NOT NULL DEFAULT now(),
            md_m numeric CHECK (md_m >= 0),
            tvd_m numeric CHECK (tvd_m >= 0),
            channels jsonb NOT NULL DEFAULT '{}'::jsonb,
            quality text,
            UNIQUE (replay_session_id, sequence)
        );
        CREATE INDEX idx_telemetry_wellbore_time ON telemetry_sample(wellbore_id, observed_at);
        CREATE TABLE interval_mapping (
            id uuid PRIMARY KEY,
            source_event_id uuid NOT NULL REFERENCES drilling_event(id),
            target_interval_id uuid NOT NULL REFERENCES formation_interval(id),
            source_event_version integer NOT NULL,
            target_interval_version integer NOT NULL,
            mapped_start_md_m numeric,
            mapped_end_md_m numeric,
            method text NOT NULL,
            method_version text NOT NULL,
            status text NOT NULL CHECK (status IN ('resolved','unresolved')),
            reason text,
            CHECK (mapped_end_md_m IS NULL OR mapped_end_md_m >= mapped_start_md_m)
        );
        CREATE TABLE model_version (
            id uuid PRIMARY KEY,
            hazard_type text NOT NULL,
            version text NOT NULL,
            artifact_checksum text,
            score_kind text NOT NULL,
            horizon_m numeric,
            metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
            UNIQUE (hazard_type, version)
        );
        CREATE TABLE risk_assessment (
            id uuid PRIMARY KEY,
            replay_session_id uuid REFERENCES replay_session(id),
            model_version_id uuid REFERENCES model_version(id),
            score numeric CHECK (score BETWEEN 0 AND 1),
            score_kind text,
            confidence_description text,
            unavailable_reason text,
            assessed_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE alert (
            id uuid PRIMARY KEY,
            active_wellbore_id uuid NOT NULL REFERENCES wellbore(id),
            replay_session_id uuid NOT NULL REFERENCES replay_session(id),
            target_interval_id uuid NOT NULL REFERENCES formation_interval(id),
            hazard_type text NOT NULL,
            depth_band integer NOT NULL,
            episode_key text NOT NULL UNIQUE,
            lifecycle text NOT NULL DEFAULT 'NEW' CHECK (
                lifecycle IN ('NEW','ACKNOWLEDGED','UNDER_REVIEW','RESOLVED','DISMISSED')
            ),
            relevance text NOT NULL DEFAULT 'upcoming',
            current_md_m numeric NOT NULL,
            rule_version text NOT NULL,
            config_version text NOT NULL,
            first_seen_at timestamptz NOT NULL DEFAULT now(),
            last_seen_at timestamptz NOT NULL DEFAULT now(),
            revision integer NOT NULL DEFAULT 1 CHECK (revision > 0),
            seen_count integer NOT NULL DEFAULT 1 CHECK (seen_count > 0)
        );
        CREATE TABLE alert_evidence (
            alert_id uuid NOT NULL REFERENCES alert(id),
            event_id uuid NOT NULL REFERENCES drilling_event(id),
            interval_mapping_id uuid NOT NULL REFERENCES interval_mapping(id),
            passage_id uuid NOT NULL REFERENCES extracted_passage(id),
            event_version integer NOT NULL,
            evidence_snapshot jsonb NOT NULL,
            PRIMARY KEY (alert_id, event_id, passage_id)
        );
        CREATE TABLE alert_risk_assessment (
            alert_id uuid NOT NULL REFERENCES alert(id),
            risk_assessment_id uuid NOT NULL REFERENCES risk_assessment(id),
            PRIMARY KEY (alert_id, risk_assessment_id)
        );
        CREATE TABLE alert_feedback (
            id uuid PRIMARY KEY,
            alert_id uuid NOT NULL REFERENCES alert(id),
            actor_name text NOT NULL,
            action_taken text,
            observed_outcome text,
            adjudicated_label text,
            rationale text,
            recorded_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE review_decision (
            id uuid PRIMARY KEY,
            entity_type text NOT NULL,
            entity_id uuid NOT NULL,
            entity_version integer NOT NULL,
            actor_name text NOT NULL,
            action text NOT NULL,
            rationale text,
            recorded_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE audit_log (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            actor_name text NOT NULL,
            action text NOT NULL,
            entity_type text,
            entity_id uuid,
            details jsonb NOT NULL DEFAULT '{}'::jsonb,
            recorded_at timestamptz NOT NULL DEFAULT now()
        );
    """)


def downgrade() -> None:
    raise RuntimeError("Foundation schema downgrade is intentionally unsupported; restore from backup")
