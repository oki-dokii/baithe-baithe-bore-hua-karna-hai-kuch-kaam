"""Cited, independently reviewed pressure/mud depth bands for display only.

Revision ID: 0016_pressure_window_evidence
Revises: 0015_voice_memo
"""

from alembic import op

revision = "0016_pressure_window_evidence"
down_revision = "0015_voice_memo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE pressure_window_evidence (
            id uuid PRIMARY KEY,
            wellbore_id uuid NOT NULL REFERENCES wellbore(id) ON DELETE RESTRICT,
            formation_interval_id uuid NOT NULL REFERENCES formation_interval(id) ON DELETE RESTRICT,
            top_md_m numeric NOT NULL CHECK (top_md_m>=0),
            base_md_m numeric NOT NULL CHECK (base_md_m>top_md_m),
            pore_pressure_ppg numeric NOT NULL CHECK (pore_pressure_ppg>0),
            fracture_gradient_ppg numeric NOT NULL CHECK (fracture_gradient_ppg>pore_pressure_ppg),
            mud_weight_ppg numeric NOT NULL CHECK (mud_weight_ppg>0),
            ecd_ppg numeric CHECK (ecd_ppg>0),
            pressure_passage_id uuid NOT NULL REFERENCES extracted_passage(id) ON DELETE RESTRICT,
            mud_passage_id uuid NOT NULL REFERENCES extracted_passage(id) ON DELETE RESTRICT,
            review_state text NOT NULL DEFAULT 'staged'
                CHECK (review_state IN ('staged','approved','rejected')),
            prepared_by text NOT NULL,
            reviewed_by text,
            review_reference text,
            created_at timestamptz NOT NULL DEFAULT now(),
            reviewed_at timestamptz,
            CHECK ((review_state='staged')=(reviewed_by IS NULL AND reviewed_at IS NULL)),
            CHECK (review_state='staged' OR (review_reference IS NOT NULL
                   AND length(btrim(review_reference))>0 AND reviewed_by<>prepared_by))
        );
        CREATE INDEX idx_pressure_window_bore_md
            ON pressure_window_evidence(wellbore_id,top_md_m);
        CREATE FUNCTION nwis_check_pressure_window_evidence() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE source_dataset dataset%ROWTYPE;
                formation_row formation_interval%ROWTYPE;
                datum_state text;
        BEGIN
            IF TG_OP='UPDATE' THEN
                IF OLD.review_state<>'staged'
                    OR (NEW.wellbore_id,NEW.formation_interval_id,NEW.top_md_m,NEW.base_md_m,
                        NEW.pore_pressure_ppg,NEW.fracture_gradient_ppg,NEW.mud_weight_ppg,
                        NEW.ecd_ppg,NEW.pressure_passage_id,NEW.mud_passage_id,NEW.prepared_by)
                       IS DISTINCT FROM
                       (OLD.wellbore_id,OLD.formation_interval_id,OLD.top_md_m,OLD.base_md_m,
                        OLD.pore_pressure_ppg,OLD.fracture_gradient_ppg,OLD.mud_weight_ppg,
                        OLD.ecd_ppg,OLD.pressure_passage_id,OLD.mud_passage_id,OLD.prepared_by) THEN
                    RAISE EXCEPTION 'Pressure evidence content is immutable'
                        USING ERRCODE='23514';
                END IF;
            ELSIF NEW.review_state<>'staged' THEN
                RAISE EXCEPTION 'Pressure evidence must start staged' USING ERRCODE='23514';
            END IF;
            SELECT * INTO formation_row FROM formation_interval WHERE id=NEW.formation_interval_id;
            SELECT review_state INTO datum_state FROM depth_reference
                WHERE id=formation_row.depth_reference_id;
            SELECT d.* INTO source_dataset FROM wellbore b JOIN well w ON w.id=b.well_id
                JOIN dataset d ON d.id=w.dataset_id WHERE b.id=NEW.wellbore_id;
            IF formation_row.wellbore_id IS DISTINCT FROM NEW.wellbore_id
                OR formation_row.review_state<>'approved' OR datum_state<>'approved'
                OR NEW.top_md_m<formation_row.top_md_m
                OR formation_row.base_md_m IS NULL OR NEW.base_md_m>formation_row.base_md_m
                OR NOT EXISTS (
                    SELECT 1 FROM extracted_passage p JOIN source_document d ON d.id=p.document_id
                    JOIN document_wellbore dw ON dw.document_id=d.id
                    WHERE p.id=NEW.pressure_passage_id AND dw.wellbore_id=NEW.wellbore_id
                      AND d.dataset_id=source_dataset.id)
                OR NOT EXISTS (
                    SELECT 1 FROM extracted_passage p JOIN source_document d ON d.id=p.document_id
                    JOIN document_wellbore dw ON dw.document_id=d.id
                    WHERE p.id=NEW.mud_passage_id AND dw.wellbore_id=NEW.wellbore_id
                      AND d.dataset_id=source_dataset.id) THEN
                RAISE EXCEPTION 'Pressure band needs reviewed interval and linked citations'
                    USING ERRCODE='23514';
            END IF;
            IF NEW.review_state='approved' THEN
                PERFORM 1 FROM wellbore WHERE id=NEW.wellbore_id FOR UPDATE;
                IF EXISTS (SELECT 1 FROM pressure_window_evidence other
                           WHERE other.wellbore_id=NEW.wellbore_id AND other.id<>NEW.id
                             AND other.review_state='approved'
                             AND other.top_md_m<NEW.base_md_m
                             AND other.base_md_m>NEW.top_md_m) THEN
                    RAISE EXCEPTION 'Reviewed pressure bands overlap' USING ERRCODE='23514';
                END IF;
                IF NOT ((source_dataset.kind='synthetic' AND source_dataset.origin_kind='synthetic'
                            AND source_dataset.applicability='demo_only')
                    OR (source_dataset.kind<>'synthetic'
                        AND source_dataset.qualification_status='qualified'
                        AND source_dataset.origin_kind IN ('operator_record','public_primary')
                        AND source_dataset.authorization_state IN
                            ('public_permitted','restricted_authorized')
                        AND source_dataset.applicability IN ('direct_offset','analog_only'))) THEN
                    RAISE EXCEPTION 'Unqualified pressure source' USING ERRCODE='23514';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM app_user WHERE username=NEW.reviewed_by
                               AND active AND role IN ('reviewer','admin')) THEN
                    RAISE EXCEPTION 'Pressure reviewer must be active'
                        USING ERRCODE='23514';
                END IF;
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER check_pressure_window_evidence
            BEFORE INSERT OR UPDATE ON pressure_window_evidence
            FOR EACH ROW EXECUTE FUNCTION nwis_check_pressure_window_evidence();
        CREATE FUNCTION nwis_reject_pressure_evidence_delete() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Pressure evidence cannot be deleted' USING ERRCODE='23514';
        END $$;
        CREATE TRIGGER immutable_pressure_window_delete
            BEFORE DELETE ON pressure_window_evidence
            FOR EACH ROW EXECUTE FUNCTION nwis_reject_pressure_evidence_delete();
    """)


def downgrade() -> None:
    raise RuntimeError("Pressure evidence review history is retained; restore a backup")
