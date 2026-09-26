"""Phase 5 qualification, not inference. Never convert unqualified data into risk."""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from nwis.db import connection
from nwis.security import current_principal

router = APIRouter(prefix="/api/v1")
FEATURES = (
    "rop_m_per_h",
    "wob_kn",
    "rpm",
    "torque_kn_m",
    "flow_in_l_per_min",
    "mud_density_kg_per_m3",
)


class Window(BaseModel):
    """One pre-onset forward-drilling window, prepared by a reviewed adapter."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    sample_id: str = Field(min_length=1)
    physical_well_id: str = Field(min_length=1)
    wellbore_id: str = Field(min_length=1)
    split: Literal["train", "validation", "test"]
    anchor_md_m: float = Field(ge=0)
    feature_end_md_m: float = Field(ge=0)
    observed_through_md_m: float = Field(ge=0)
    next_loss_md_m: float | None = Field(default=None, ge=0)
    label_reviewed: bool
    label_source: str = Field(min_length=1)
    features: dict[str, float]

    @model_validator(mode="after")
    def chronology(self):
        if self.feature_end_md_m > self.anchor_md_m:
            raise ValueError("Future feature leakage")
        if self.observed_through_md_m < self.anchor_md_m + 100:
            raise ValueError("Censored 100 m outcome window")
        if self.next_loss_md_m is not None and not (
            self.anchor_md_m < self.next_loss_md_m <= self.observed_through_md_m
        ):
            raise ValueError("Loss must be after anchor and within observed coverage")
        if set(self.features) != set(FEATURES):
            raise ValueError("Feature names/units must match mud-loss-features-v1")
        if any(value < 0 for value in self.features.values()):
            raise ValueError("Feature values must be nonnegative")
        return self

    @property
    def label(self):
        return int(
            self.next_loss_md_m is not None and self.next_loss_md_m <= self.anchor_md_m + 100
        )


class DatasetManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["mud-loss-windows-v1"]
    kind: Literal["synthetic", "public", "private"]
    source_reference: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    permission_reference: str = Field(min_length=1)
    domain_reviewed: bool
    windows: list[Window] = Field(min_length=1, max_length=100000)


def audit(manifest: DatasetManifest):
    blockers = []
    groups = defaultdict(set)
    bore_groups = defaultdict(set)
    ids = Counter(w.sample_id for w in manifest.windows)
    anchors = Counter((w.wellbore_id, w.anchor_md_m) for w in manifest.windows)
    for window in manifest.windows:
        groups[window.physical_well_id].add(window.split)
        bore_groups[window.wellbore_id].add(window.physical_well_id)
    if any(len(splits) > 1 for splits in groups.values()):
        blockers.append("physical_well_split_leakage")
    if any(len(wells) > 1 for wells in bore_groups.values()):
        blockers.append("inconsistent_wellbore_parent")
    if max(ids.values()) > 1 or max(anchors.values()) > 1:
        blockers.append("duplicate_samples")
    if manifest.kind == "synthetic":
        blockers.append("synthetic_only_not_real_validation")
    if not manifest.domain_reviewed:
        blockers.append("domain_review_required")
    if not all(w.label_reviewed for w in manifest.windows):
        blockers.append("unreviewed_labels")
    partitions = {}
    for split in ("train", "validation", "test"):
        rows = [w for w in manifest.windows if w.split == split]
        wells = len({w.physical_well_id for w in rows})
        positive = sum(w.label for w in rows)
        partitions[split] = {
            "samples": len(rows),
            "physical_wells": wells,
            "positive": positive,
            "negative": len(rows) - positive,
        }
        # A structural floor only, not evidence of statistical sufficiency.
        if wells < 2 or positive == 0 or positive == len(rows):
            blockers.append(f"{split}_insufficient_class_or_well_coverage")
    digest = hashlib.sha256(manifest.model_dump_json().encode()).hexdigest()
    return {
        "manifest_sha256": digest,
        "hazard": "mud_loss",
        "horizon_m": 100,
        "feature_schema": "mud-loss-features-v1",
        "partitions": partitions,
        "blockers": blockers,
        "structural_checks_passed": not blockers,
        "training_authorized": False,
        "operationally_validated": False,
        "next_gate": "Independent source, label, chronology and sample-size review before training",
        "limitations": "Metadata checks cannot prove source accuracy, feature-time availability, or independent wells.",
    }


def model_card():
    return {
        "hazard": "mud_loss",
        "horizon_m": 100,
        "state": "awaiting_qualified_data",
        "model_version": None,
        "score": None,
        "score_kind": "unavailable",
        "reason": "model_not_available",
        "metrics": None,
        "calibration": None,
        "features": list(FEATURES),
        "gates": [
            "Qualify permitted telemetry and reviewed onset/negative coverage",
            "Keep physical wells and all sidetracks in one split",
            "Fit transforms on training wells; tune on validation wells",
            "Compare a model with a prevalence baseline on untouched test wells",
            "Review uncertainty and calibration before probability display",
        ],
        "note": "Historical alerts are rules, not model predictions. No trained artifact is deployed.",
    }


@router.get("/prediction/readiness")
def readiness(_principal=Depends(current_principal)):
    with connection() as conn:
        counts = conn.execute("""SELECT d.kind, count(*) AS approved_events,
            count(DISTINCT b.well_id) AS physical_wells
            FROM drilling_event e JOIN wellbore b ON b.id=e.wellbore_id
            JOIN well w ON w.id=b.well_id JOIN dataset d ON d.id=w.dataset_id
            WHERE e.event_type='mud_loss' AND e.review_state='approved' GROUP BY d.kind""").fetchall()
    return {
        **model_card(),
        "historical_inventory": counts,
        "inventory_note": "Reviewed report events are not automatically predictive training windows or negative labels.",
    }


@router.get("/risk/current/{wellbore_id}")
def current_risk(wellbore_id: UUID, _principal=Depends(current_principal)):
    with connection() as conn:
        if not conn.execute("SELECT 1 FROM wellbore WHERE id=%s", (wellbore_id,)).fetchone():
            raise HTTPException(404, "Wellbore not found")
    return {"wellbore_id": str(wellbore_id), **model_card()}


def main():
    parser = argparse.ArgumentParser(
        description="Audit prepared JSON windows locally; never trains or uploads data"
    )
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    manifest = DatasetManifest.model_validate_json(args.manifest.read_text())
    report = audit(manifest)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["structural_checks_passed"] else 2)


if __name__ == "__main__":
    main()
