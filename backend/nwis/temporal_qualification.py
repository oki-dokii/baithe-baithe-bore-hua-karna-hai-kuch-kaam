"""Offline audit of reviewer-asserted pre-event telemetry windows; never trains."""

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


class Window(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_id: str = Field(min_length=1)
    physical_well_id: str = Field(min_length=1)
    wellbore_id: str = Field(min_length=1)
    split: Literal["train", "validation", "test"]
    label: Literal["positive", "negative"]
    window_start: datetime
    window_end: datetime
    coverage_start: datetime
    coverage_end: datetime
    coverage_source: str = Field(min_length=1)
    coverage_reviewed: bool
    event_free_reviewed: bool = False
    event_id: str | None = None
    onset_earliest: datetime | None = None
    onset_latest: datetime | None = None
    onset_basis: Literal["exact_timelog", "day_only_ddr", "shift_report", "unspecified"] | None = None

    @model_validator(mode="after")
    def valid_window(self):
        times = [self.window_start, self.window_end, self.coverage_start, self.coverage_end]
        times += [v for v in (self.onset_earliest, self.onset_latest) if v is not None]
        if not all(aware(value) for value in times):
            raise ValueError("All time bounds require an explicit UTC offset")
        if self.window_start >= self.window_end:
            raise ValueError("Window start must precede end")
        if self.coverage_start > self.window_start or self.coverage_end < self.window_end:
            raise ValueError("Telemetry window must lie inside reviewed coverage bounds")
        if self.label == "positive":
            if not all((self.event_id, self.onset_earliest, self.onset_latest)):
                raise ValueError("Positive window needs an event and both onset bounds")
            if self.onset_basis in (None, "unspecified"):
                raise ValueError("Positive window needs a timed onset basis")
            if self.onset_earliest > self.onset_latest:
                raise ValueError("Invalid onset interval")
            if self.onset_basis == "exact_timelog" and self.onset_earliest != self.onset_latest:
                raise ValueError("Exact timelog bounds must be equal")
        elif any(v is not None for v in (self.event_id, self.onset_earliest, self.onset_latest, self.onset_basis)):
            raise ValueError("Negative window must not carry an event onset")
        return self


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["temporal-qualification-v1"]
    source_kind: Literal["synthetic", "public", "private"]
    source_reference: str = Field(min_length=1)
    permission_reference: str = Field(min_length=1)
    hazard: Literal["mud_loss", "stuck_pipe", "kick"]
    horizon_minutes: int = Field(gt=0)
    domain_reviewed: bool
    windows: list[Window] = Field(min_length=1)


def audit(manifest: Manifest) -> dict:
    horizon = timedelta(minutes=manifest.horizon_minutes)
    blockers: list[str] = []
    partitions: dict[str, dict] = {}
    group_splits: dict[str, set[str]] = defaultdict(set)
    bore_parents: dict[str, set[str]] = defaultdict(set)
    sample_ids = Counter(window.sample_id for window in manifest.windows)
    positive_wells: set[str] = set()
    negative_only_wells: set[str] = set()
    wells_with_positive = {w.physical_well_id for w in manifest.windows if w.label == "positive"}

    for window in manifest.windows:
        group_splits[window.physical_well_id].add(window.split)
        bore_parents[window.wellbore_id].add(window.physical_well_id)
        if not window.coverage_reviewed:
            blockers.append("unreviewed_coverage")
        if window.label == "positive":
            positive_wells.add(window.physical_well_id)
            if not window.window_end < window.onset_earliest:
                blockers.append("pre_event_cutoff_violated")
            if window.onset_latest > window.window_end + horizon:
                blockers.append("onset_not_certain_within_horizon")
            if window.coverage_end < window.onset_latest:
                blockers.append("positive_outcome_coverage_gap")
        else:
            if not window.event_free_reviewed:
                blockers.append("negative_event_free_review_required")
            if window.coverage_end < window.window_end + horizon:
                blockers.append("negative_future_horizon_not_covered")
            if window.physical_well_id not in wells_with_positive:
                negative_only_wells.add(window.physical_well_id)

    if any(len(splits) > 1 for splits in group_splits.values()):
        blockers.append("physical_well_split_leakage")
    if any(len(parents) > 1 for parents in bore_parents.values()):
        blockers.append("inconsistent_wellbore_parent")
    if max(sample_ids.values()) > 1:
        blockers.append("duplicate_samples")
    if len(positive_wells) < 2:
        blockers.append("fewer_than_two_positive_physical_wells")
    if not negative_only_wells:
        blockers.append("no_negative_only_physical_well")
    if manifest.source_kind == "synthetic":
        blockers.append("synthetic_only")
    if not manifest.domain_reviewed:
        blockers.append("domain_review_required")
    for split in ("train", "validation", "test"):
        rows = [w for w in manifest.windows if w.split == split]
        positives = sum(w.label == "positive" for w in rows)
        partitions[split] = {
            "windows": len(rows),
            "physical_wells": len({w.physical_well_id for w in rows}),
            "positive_windows": positives,
            "negative_windows": len(rows) - positives,
            "positive_physical_wells": len({w.physical_well_id for w in rows if w.label == "positive"}),
        }
        if not rows or positives == 0 or positives == len(rows):
            blockers.append(f"{split}_class_coverage_missing")
    return {
        "schema_version": manifest.schema_version,
        "hazard": manifest.hazard,
        "horizon_minutes": manifest.horizon_minutes,
        "partitions": partitions,
        "positive_physical_wells": len(positive_wells),
        "negative_only_physical_wells": len(negative_only_wells),
        "blockers": sorted(set(blockers)),
        "structural_checks_passed": not blockers,
        "training_authorized": False,
        "note": "Review and coverage fields are source assertions, not verified by this metadata-only audit.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit reviewed temporal window metadata locally")
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    report = audit(Manifest.model_validate_json(args.manifest.read_text()))
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["structural_checks_passed"] else 2)


if __name__ == "__main__":
    main()
