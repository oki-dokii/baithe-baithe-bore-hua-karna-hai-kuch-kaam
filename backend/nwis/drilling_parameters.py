"""Stage provenance-preserving historical samples; never qualify a source implicitly."""

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from psycopg import Connection
from psycopg.types.json import Jsonb

from nwis.db import connection


class DrillingScreenError(ValueError):
    def __init__(self, report: dict):
        self.report = report
        super().__init__("drilling_ahead_screen_stopped_import")


class HistoricalSample(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    wellbore_id: UUID
    source_record_id: str = Field(min_length=1, max_length=240)
    revision: int = Field(ge=1)
    operation: Literal["upsert", "delete"] = "upsert"
    observed_at: datetime
    available_at: datetime
    received_at: datetime
    md_m: float | None = Field(default=None, ge=0)
    tvd_m: float | None = Field(default=None, ge=0)
    depth_reference_id: UUID | None = None
    rig_state: Literal["forward_drilling", "circulating", "tripping", "other", "unknown"]
    quality: Literal["good", "suspect", "bad", "missing"]
    source_quality_code: str | None = None
    rop_m_per_h: float | None = Field(default=None, ge=0)
    wob_kn: float | None = Field(default=None, ge=0)
    rpm: float | None = Field(default=None, ge=0)
    torque_kn_m: float | None = Field(default=None, ge=0)
    flow_in_l_per_min: float | None = Field(default=None, ge=0)
    mud_density_kg_per_m3: float | None = Field(default=None, gt=0)
    raw_values: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_times_and_operation(self):
        times = (self.observed_at, self.available_at, self.received_at)
        if any(t.tzinfo is None or t.utcoffset() is None for t in times):
            raise ValueError("Historical timestamps require explicit timezones")
        if not times[0] <= times[1] <= times[2]:
            raise ValueError("Expected observed <= available <= received")
        channels = ("rop_m_per_h", "wob_kn", "rpm", "torque_kn_m",
                    "flow_in_l_per_min", "mud_density_kg_per_m3")
        if self.operation == "upsert" and self.md_m is None:
            raise ValueError("Upsert needs measured depth")
        if self.operation == "delete" and (
            self.revision == 1 or self.quality != "missing"
            or any(getattr(self, channel) is not None for channel in channels)
        ):
            raise ValueError("Correction tombstone must have missing quality and no channels")
        return self


class HistoricalBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["historical-drilling-parameters-v1"]
    dataset_id: UUID
    external_id: str = Field(min_length=1, max_length=240)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_kind: Literal["witsml_export", "csv_export", "other"]
    source_reference: str = Field(min_length=1)
    permission_reference: str = Field(min_length=1)
    source_timezone: str = Field(min_length=1)
    md_datum: str = Field(min_length=1)
    source_units: dict[str, str]
    mapping_version: str = Field(min_length=1)
    samples: list[HistoricalSample] = Field(min_length=1)


def stage_batch(conn: Connection, batch: HistoricalBatch, source_bytes: bytes) -> dict:
    """Idempotently stage rows from a checksum-verified source, in one transaction.

    The caller owns the transaction. Corrections append revisions; changing an
    existing revision or source mapping is an error, never an overwrite.
    """
    if hashlib.sha256(source_bytes).hexdigest() != batch.source_sha256:
        raise ValueError("source_checksum_mismatch")
    dataset = conn.execute("SELECT kind FROM dataset WHERE id=%s", (batch.dataset_id,)).fetchone()
    if dataset is None or dataset["kind"] == "synthetic":
        raise ValueError("historical_source_requires_non_synthetic_dataset")
    identity = ("dataset_id", "external_id", "source_sha256", "source_kind",
                "source_reference", "permission_reference", "source_timezone",
                "md_datum", "source_units", "mapping_version")
    # Check both unique identities, so a changed checksum cannot silently
    # become a second version of the same external source.
    existing = conn.execute(
        """SELECT * FROM drilling_parameter_source
           WHERE (dataset_id=%s AND external_id=%s)
              OR (dataset_id=%s AND source_sha256=%s) FOR UPDATE""",
        (batch.dataset_id, batch.external_id, batch.dataset_id, batch.source_sha256),
    ).fetchall()
    if len(existing) > 1:
        raise ValueError("source_identity_collision")
    expected = batch.model_dump(exclude={"samples", "schema_version"})
    if existing:
        source = existing[0]
        if any(source[key] != expected[key] for key in identity):
            raise ValueError("source_identity_or_mapping_changed")
        if source["qualification_state"] != "staged":
            raise ValueError("source_no_longer_staged")
        source_id = source["id"]
        prior_rows = conn.execute(
            """SELECT wellbore_id,source_record_id,revision,operation,
                      observed_at,available_at,received_at,md_m,tvd_m,
                      depth_reference_id,rig_state,quality,source_quality_code,
                      rop_m_per_h,wob_kn,rpm,torque_kn_m,flow_in_l_per_min,
                      mud_density_kg_per_m3,raw_values
               FROM drilling_parameter_sample WHERE source_id=%s""",
            (source_id,),
        ).fetchall()
    else:
        source_id = uuid4()
        prior_rows = []
    # Screen the full effective state, including staged correction history.
    # No insert happens unless every wellbore still passes.
    from nwis.telemetry_screen import screen_batch

    report = screen_batch(
        [HistoricalSample.model_validate(row) for row in prior_rows] + batch.samples
    )
    if report["decision"] == "stop":
        raise DrillingScreenError(report)
    if not existing:
        conn.execute(
            """INSERT INTO drilling_parameter_source
               (id,dataset_id,external_id,source_sha256,source_kind,source_reference,
                permission_reference,source_timezone,md_datum,source_units,mapping_version)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (source_id, batch.dataset_id, batch.external_id, batch.source_sha256,
             batch.source_kind, batch.source_reference, batch.permission_reference,
             batch.source_timezone, batch.md_datum, Jsonb(batch.source_units),
             batch.mapping_version),
        )
    staged = 0
    for sample in batch.samples:
        payload = sample.model_dump(mode="json")
        row_sha = hashlib.sha256(json.dumps(payload, sort_keys=True,
                                            separators=(",", ":")).encode()).hexdigest()
        old = conn.execute(
            """SELECT id,row_sha256 FROM drilling_parameter_sample
               WHERE source_id=%s AND source_record_id=%s AND revision=%s""",
            (source_id, sample.source_record_id, sample.revision),
        ).fetchone()
        if old:
            if old["row_sha256"] != row_sha:
                raise ValueError("sample_revision_changed")
            continue
        conn.execute(
            """INSERT INTO drilling_parameter_sample
               (id,source_id,wellbore_id,source_record_id,revision,operation,
                observed_at,available_at,received_at,md_m,tvd_m,depth_reference_id,
                rig_state,quality,source_quality_code,rop_m_per_h,wob_kn,rpm,
                torque_kn_m,flow_in_l_per_min,mud_density_kg_per_m3,raw_values,row_sha256)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (uuid4(), source_id, sample.wellbore_id, sample.source_record_id,
             sample.revision, sample.operation, sample.observed_at, sample.available_at,
             sample.received_at, sample.md_m, sample.tvd_m, sample.depth_reference_id,
             sample.rig_state, sample.quality, sample.source_quality_code,
             sample.rop_m_per_h, sample.wob_kn, sample.rpm, sample.torque_kn_m,
             sample.flow_in_l_per_min, sample.mud_density_kg_per_m3,
             Jsonb(sample.raw_values), row_sha),
        )
        staged += 1
    return {"source_id": str(source_id), "staged_rows": staged,
            "qualification_state": "staged"}


def eligible_anchors(conn: Connection, source_id: UUID) -> list[dict]:
    """Return only current, qualified, reviewed-reference forward-drilling rows.

    These are sensor candidates, not labels or reviewed coverage. Callers must
    provide an explicit well-level split before using TelemetryAnchor.
    """
    return conn.execute(
        """SELECT s.id AS sample_id, s.source_record_id, s.wellbore_id,
                  w.id AS physical_well_id, s.observed_at, s.available_at, s.md_m,
                  s.rop_m_per_h, s.wob_kn, s.rpm, s.torque_kn_m,
                  s.flow_in_l_per_min, s.mud_density_kg_per_m3
           FROM drilling_parameter_sample s
           JOIN drilling_parameter_source src ON src.id=s.source_id
           JOIN dataset d ON d.id=src.dataset_id
           JOIN wellbore b ON b.id=s.wellbore_id
           JOIN well w ON w.id=b.well_id AND w.dataset_id=d.id
           JOIN depth_reference ref ON ref.id=s.depth_reference_id
           WHERE src.id=%s AND src.qualification_state='qualified'
             AND src.units_reviewed AND src.timezone_reviewed AND src.datum_reviewed
             AND d.kind IN ('public','private') AND d.qualification_status='qualified'
             AND d.origin_kind IN ('operator_record','public_primary')
             AND d.authorization_state IN ('public_permitted','restricted_authorized')
             AND d.applicability IN ('direct_offset','analog_only')
             AND ref.review_state='approved' AND s.operation='upsert'
             AND s.quality='good' AND s.rig_state='forward_drilling'
             AND s.rop_m_per_h IS NOT NULL AND s.wob_kn IS NOT NULL
             AND s.rpm IS NOT NULL AND s.torque_kn_m IS NOT NULL
             AND s.flow_in_l_per_min IS NOT NULL
             AND NOT EXISTS (SELECT 1 FROM drilling_parameter_sample newer
                 WHERE newer.source_id=s.source_id
                   AND newer.source_record_id=s.source_record_id
                   AND newer.revision>s.revision)
           ORDER BY s.observed_at,s.id""",
        (source_id,),
    ).fetchall()


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage historical drilling parameters")
    parser.add_argument("--source-file", required=True, type=Path)
    parser.add_argument("--batch", required=True, type=Path)
    parser.add_argument("--screen-only", action="store_true")
    args = parser.parse_args()
    batch = HistoricalBatch.model_validate_json(args.batch.read_text())
    source_bytes = args.source_file.read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != batch.source_sha256:
        parser.error("source checksum does not match batch")
    if args.screen_only:
        from nwis.telemetry_screen import screen_batch

        report = screen_batch(batch.samples)
        print(json.dumps(report, sort_keys=True))
        if report["decision"] == "stop":
            raise SystemExit(2)
        return
    with connection() as conn:
        try:
            result = stage_batch(conn, batch, source_bytes)
        except DrillingScreenError as exc:
            print(json.dumps(exc.report, sort_keys=True))
            raise SystemExit(2) from exc
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
