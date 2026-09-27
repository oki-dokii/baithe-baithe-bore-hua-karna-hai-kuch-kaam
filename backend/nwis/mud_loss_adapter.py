"""Offline, fail-closed adapter from reviewed source assertions to mud-loss windows.

This does not read the replay telemetry table or qualify any real source by itself.
"""

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from nwis.prediction import DatasetManifest, FEATURES, Window, audit

HORIZON_M = 100
SENSOR_FEATURES = tuple(name for name in FEATURES if name != "mud_density_kg_per_m3")


def aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


class TelemetryAnchor(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    sample_id: str = Field(min_length=1)
    physical_well_id: str = Field(min_length=1)
    wellbore_id: str = Field(min_length=1)
    split: Literal["train", "validation", "test"]
    observed_at: datetime
    available_at: datetime
    md_m: float = Field(ge=0)
    quality: Literal["good"]
    rig_state: Literal["forward_drilling"]
    source_record_id: str = Field(min_length=1)
    features: dict[str, float]

    @model_validator(mode="after")
    def check_features(self):
        if not aware(self.observed_at) or not aware(self.available_at):
            raise ValueError("Telemetry anchor needs timezone-aware observation and availability")
        if self.available_at < self.observed_at:
            raise ValueError("Sensor availability cannot precede observation")
        if set(self.features) != set(SENSOR_FEATURES):
            raise ValueError("Telemetry features need exactly the five canonical sensor channels")
        if any(value < 0 for value in self.features.values()):
            raise ValueError("Sensor features must be nonnegative")
        return self


class MudDensityRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    wellbore_id: str = Field(min_length=1)
    source_record_id: str = Field(min_length=1)
    source_kind: Literal["measured_sensor", "reviewed_mud_program"]
    recorded_at: datetime
    effective_from: datetime
    effective_until: datetime | None = None
    top_md_m: float = Field(ge=0)
    base_md_m: float = Field(gt=0)
    mud_density_kg_per_m3: float = Field(gt=0)
    reviewed: bool

    @model_validator(mode="after")
    def check_interval(self):
        if not all(aware(time) for time in (self.recorded_at, self.effective_from)):
            raise ValueError("Mud-density provenance needs timezone-aware times")
        if self.effective_until is not None and (
            not aware(self.effective_until) or self.effective_until <= self.effective_from
        ):
            raise ValueError("Invalid mud-density effective interval")
        if self.base_md_m <= self.top_md_m:
            raise ValueError("Invalid mud-density depth interval")
        return self


class ReviewedCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    wellbore_id: str = Field(min_length=1)
    source_reference: str = Field(min_length=1)
    top_md_m: float = Field(ge=0)
    base_md_m: float = Field(gt=0)
    from_time: datetime
    observed_through_at: datetime
    reviewed: bool
    event_free_reviewed: bool

    @model_validator(mode="after")
    def check_interval(self):
        if not aware(self.from_time) or not aware(self.observed_through_at):
            raise ValueError("Coverage needs timezone-aware times")
        if self.observed_through_at <= self.from_time or self.base_md_m <= self.top_md_m:
            raise ValueError("Invalid coverage interval")
        return self


class ReviewedLoss(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    event_id: str = Field(min_length=1)
    wellbore_id: str = Field(min_length=1)
    onset_md_m: float = Field(ge=0)
    onset_earliest: datetime | None = None
    onset_latest: datetime | None = None
    onset_basis: Literal["exact_timelog", "day_only_ddr", "shift_report", "unspecified"]
    event_reviewed: bool
    source_passage_id: str = Field(min_length=1)
    depth_datum_reviewed: bool

    @model_validator(mode="after")
    def check_onset(self):
        if self.onset_earliest is not None and not aware(self.onset_earliest):
            raise ValueError("Onset earliest needs an explicit timezone")
        if self.onset_latest is not None and not aware(self.onset_latest):
            raise ValueError("Onset latest needs an explicit timezone")
        if self.onset_earliest and self.onset_latest and self.onset_earliest > self.onset_latest:
            raise ValueError("Reversed onset bounds")
        return self


class SourceBundle(BaseModel):
    """A source-specific importer must substantiate every assertion in this bundle."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["mud-loss-adapter-input-v1"]
    kind: Literal["synthetic", "public", "private"]
    source_reference: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    permission_reference: str = Field(min_length=1)
    domain_reviewed: bool
    anchors: list[TelemetryAnchor] = Field(min_length=1)
    mud_density: list[MudDensityRecord]
    coverage: list[ReviewedCoverage]
    losses: list[ReviewedLoss]


class AdapterError(ValueError):
    def __init__(self, code: str, sample_id: str):
        self.code = code
        self.sample_id = sample_id
        super().__init__(code)


def exactly_one(rows: list, *, missing: str, ambiguous: str, sample_id: str):
    if not rows:
        raise AdapterError(missing, sample_id)
    if len(rows) != 1:
        raise AdapterError(ambiguous, sample_id)
    return rows[0]


def build_window(bundle: SourceBundle, anchor: TelemetryAnchor) -> Window:
    horizon_end = anchor.md_m + HORIZON_M
    density = exactly_one(
        [
            item
            for item in bundle.mud_density
            if item.wellbore_id == anchor.wellbore_id
            and item.reviewed
            and item.recorded_at <= anchor.available_at
            and item.effective_from <= anchor.observed_at
            and (item.effective_until is None or anchor.observed_at < item.effective_until)
            and item.top_md_m <= anchor.md_m < item.base_md_m
        ],
        missing="reviewed_pre_anchor_mud_density_missing",
        ambiguous="overlapping_mud_density_records",
        sample_id=anchor.sample_id,
    )
    coverage = exactly_one(
        [
            item
            for item in bundle.coverage
            if item.wellbore_id == anchor.wellbore_id
            and item.reviewed
            and item.top_md_m <= anchor.md_m
            and item.base_md_m >= horizon_end
            and item.from_time <= anchor.observed_at < item.observed_through_at
        ],
        missing="reviewed_future_coverage_missing",
        ambiguous="overlapping_coverage_records",
        sample_id=anchor.sample_id,
    )
    future_losses = [
        event
        for event in bundle.losses
        if event.wellbore_id == anchor.wellbore_id and anchor.md_m < event.onset_md_m <= horizon_end
    ]
    if len(future_losses) > 1:
        raise AdapterError("multiple_loss_onsets_in_horizon_need_adjudication", anchor.sample_id)
    event = future_losses[0] if future_losses else None
    if event:
        if not event.event_reviewed or not event.depth_datum_reviewed:
            raise AdapterError("loss_event_review_missing", anchor.sample_id)
        if (
            event.onset_basis == "unspecified"
            or event.onset_earliest is None
            or event.onset_latest is None
        ):
            raise AdapterError("timed_loss_onset_missing", anchor.sample_id)
        if event.onset_earliest <= anchor.available_at:
            raise AdapterError("positive_feature_time_leakage_or_uncertain_onset", anchor.sample_id)
        if event.onset_latest > coverage.observed_through_at:
            raise AdapterError("positive_outcome_time_not_covered", anchor.sample_id)
        if coverage.event_free_reviewed:
            raise AdapterError("coverage_conflicts_with_loss_event", anchor.sample_id)
        label_source = f"reviewed_event:{event.event_id};passage:{event.source_passage_id}"
    else:
        if not coverage.event_free_reviewed:
            raise AdapterError("negative_event_free_review_missing", anchor.sample_id)
        label_source = f"reviewed_event_free_coverage:{coverage.source_reference}"
    return Window(
        sample_id=anchor.sample_id,
        physical_well_id=anchor.physical_well_id,
        wellbore_id=anchor.wellbore_id,
        split=anchor.split,
        anchor_md_m=anchor.md_m,
        feature_end_md_m=anchor.md_m,
        observed_through_md_m=coverage.base_md_m,
        next_loss_md_m=event.onset_md_m if event else None,
        label_reviewed=True,
        label_source=label_source,
        features={**anchor.features, "mud_density_kg_per_m3": density.mud_density_kg_per_m3},
    )


def build_manifest(bundle: SourceBundle) -> DatasetManifest:
    ids = Counter(anchor.sample_id for anchor in bundle.anchors)
    if max(ids.values()) > 1:
        raise AdapterError(
            "duplicate_anchor_sample_id", next(key for key, count in ids.items() if count > 1)
        )
    windows = [build_window(bundle, anchor) for anchor in bundle.anchors]
    return DatasetManifest(
        schema_version="mud-loss-windows-v1",
        kind=bundle.kind,
        source_reference=bundle.source_reference,
        source_sha256=bundle.source_sha256,
        permission_reference=bundle.permission_reference,
        domain_reviewed=bundle.domain_reviewed,
        windows=windows,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build reviewed-assertion mud-loss windows offline; never trains a model"
    )
    parser.add_argument("source", type=Path)
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Explicit local output path; do not commit real data",
    )
    args = parser.parse_args()
    try:
        source = SourceBundle.model_validate_json(args.source.read_text())
        manifest = build_manifest(source)
    except (ValidationError, AdapterError) as exc:
        code = exc.code if isinstance(exc, AdapterError) else "source_schema_invalid"
        print(json.dumps({"error_code": code, "training_authorized": False}), file=sys.stderr)
        raise SystemExit(2) from None
    report = audit(manifest)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(manifest.model_dump_json(indent=2))
    print(
        json.dumps(
            {
                "windows": len(manifest.windows),
                "kind": manifest.kind,
                "structural_checks_passed": report["structural_checks_passed"],
                "blockers": report["blockers"],
                "training_authorized": False,
            },
            indent=2,
        )
    )
    raise SystemExit(0 if report["structural_checks_passed"] else 2)


if __name__ == "__main__":
    main()
