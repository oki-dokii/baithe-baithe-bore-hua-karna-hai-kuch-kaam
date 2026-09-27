"""Audit a locally prepared Volve file inventory; never infer event labels from filenames."""

import argparse
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WellboreInventory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    physical_well_id: str = Field(min_length=1)
    wellbore_id: str = Field(min_length=1)
    ddr_refs: list[str] = Field(default_factory=list)
    telemetry_refs: list[str] = Field(default_factory=list)
    time_depth_join_reviewed: bool = False
    reviewed_loss_onsets: int = Field(default=0, ge=0)
    reviewed_no_event_intervals: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def unique_references(self):
        for refs in (self.ddr_refs, self.telemetry_refs):
            if any(not ref.strip() for ref in refs) or len(refs) != len(set(refs)):
                raise ValueError("File references must be nonempty and unique within each kind")
        if self.time_depth_join_reviewed and not (self.ddr_refs and self.telemetry_refs):
            raise ValueError("A reviewed join requires both DDR and telemetry references")
        return self


class Inventory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["volve-overlap-v1"]
    inventory_reference: str = Field(min_length=1)
    source_kind: Literal["synthetic_example", "public_metadata"]
    wellbores: list[WellboreInventory]

    @model_validator(mode="after")
    def unique_wellbores(self):
        ids = [wellbore.wellbore_id for wellbore in self.wellbores]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate wellbore IDs")
        return self


def audit(inventory: Inventory) -> dict:
    overlapping = [w for w in inventory.wellbores if w.ddr_refs and w.telemetry_refs]
    joined = [w for w in overlapping if w.time_depth_join_reviewed]
    labeled = [
        w for w in joined if w.reviewed_loss_onsets and w.reviewed_no_event_intervals
    ]
    blockers = []
    if not overlapping:
        blockers.append("no_ddr_telemetry_overlap")
    if len(joined) < len(overlapping):
        blockers.append("time_depth_joins_not_reviewed")
    if not labeled:
        blockers.append("no_joined_wellbore_with_reviewed_positive_and_negative_coverage")
    if inventory.source_kind == "synthetic_example":
        blockers.append("synthetic_example_not_real_source")
    return {
        "schema_version": inventory.schema_version,
        "source_kind": inventory.source_kind,
        "wellbores_in_inventory": len(inventory.wellbores),
        "physical_wells_in_inventory": len({w.physical_well_id for w in inventory.wellbores}),
        "wellbores_with_ddr_and_telemetry": len(overlapping),
        "physical_wells_with_ddr_and_telemetry": len({w.physical_well_id for w in overlapping}),
        "reviewed_time_depth_joins": len(joined),
        "joined_wellbores_with_reviewed_positive_and_negative_coverage": len(labeled),
        "blockers": blockers,
        "training_authorized": False,
        "note": "Inventory assertions are not verified against source files or domain-reviewed here.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit local Volve DDR/telemetry overlap metadata")
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    inventory = Inventory.model_validate_json(args.manifest.read_text())
    print(json.dumps(audit(inventory), indent=2))


if __name__ == "__main__":
    main()
