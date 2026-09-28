"""Offline mapper for the original Utah FORGE 56-32 10-second Pason CSV.

No data is downloaded. This prepares one explicitly bounded drilling interval
for historical staging; source rights, units and depth semantics remain review
assertions rather than automatic engineering approval.
"""

import argparse
import csv
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator

from nwis.drilling_parameters import HistoricalBatch, HistoricalSample
from nwis.telemetry_screen import screen_batch

SOURCE_URL = "https://gdr.openei.org/files/1295/56-32%2010sec%20data%2027029986.csv"
STANDARD_URL = "https://gdr.openei.org/files/1295/56-32%2010sec%20data%2027029986_standard.csv"
REQUIRED = (
    "Hole Depth", "Weight on Bit", "Rotary RPM", "Convertible Torque",
    "Flow", "Rate Of Penetration", "YYYY/MM/DD", "HH:MM:SS", "On Bottom ROP",
)
UNITS = {
    "Hole Depth": "ft", "Weight on Bit": "klbf",
    "Rotary RPM": "rpm", "Convertible Torque": "kft-lbf",
    "Flow": "gpm", "Rate Of Penetration": "ft/h",
}
FT_TO_M = 0.3048
KLBF_TO_KN = 4.4482216152605
KFTLBF_TO_KNM = 1.3558179483314
GPM_TO_LPM = 3.785411784


class Forge56Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["forge-56-32-raw-10s-v1"]
    dataset_id: UUID
    wellbore_id: UUID
    depth_reference_id: UUID
    permission_reference: str = Field(min_length=1)
    source_timezone: str = Field(min_length=1)
    md_datum: str = Field(min_length=1)
    depth_semantics_reference: str = Field(min_length=1)
    availability_lag_seconds: int = Field(ge=0)
    availability_reference: str = Field(min_length=1)
    unit_reference: str = Field(min_length=1)
    source_units: dict[str, str]
    start_local: datetime
    end_local: datetime

    @model_validator(mode="after")
    def explicit_mapping(self):
        try:
            ZoneInfo(self.source_timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Unknown IANA source timezone") from exc
        if self.source_units != UNITS:
            raise ValueError("The six raw channels require the verified 56-32 unit map")
        if any(t.tzinfo is not None for t in (self.start_local, self.end_local)):
            raise ValueError("Select local wall-clock bounds without timezone offsets")
        if self.end_local <= self.start_local:
            raise ValueError("Invalid local interval")
        return self


def number(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    try:
        result = float(value)
    except ValueError:
        return None
    if not (-999.25 < result < 1e12):
        return None
    return result if result >= 0 else None


def source_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare(path: Path, config: Forge56Config) -> tuple[HistoricalBatch, dict]:
    digest = source_hash(path)
    zone = ZoneInfo(config.source_timezone)
    received = datetime.now(timezone.utc)
    samples: list[HistoricalSample] = []
    skipped = {"outside_interval": 0, "missing_timestamp": 0,
               "missing_depth": 0, "invalid_numeric": 0}
    prior_md: float | None = None
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or set(REQUIRED) - set(reader.fieldnames):
            raise ValueError("56-32 raw CSV header mismatch")
        for line_number, raw in enumerate(reader, start=2):
            try:
                local = datetime.strptime(
                    f"{raw['YYYY/MM/DD']} {raw['HH:MM:SS']}", "%Y/%m/%d %H:%M:%S"
                )
            except (ValueError, TypeError):
                skipped["missing_timestamp"] += 1
                continue
            if not config.start_local <= local < config.end_local:
                skipped["outside_interval"] += 1
                continue
            observed = local.replace(tzinfo=zone).astimezone(timezone.utc)
            available = observed + timedelta(seconds=config.availability_lag_seconds)
            if available > received:
                raise ValueError("Availability would be after import receipt")
            md_ft = number(raw["Hole Depth"])
            if md_ft is None:
                skipped["missing_depth"] += 1
                continue
            md_m = md_ft * FT_TO_M
            rop = number(raw["Rate Of Penetration"])
            wob = number(raw["Weight on Bit"])
            rpm = number(raw["Rotary RPM"])
            torque = number(raw["Convertible Torque"])
            flow = number(raw["Flow"])
            on_bottom = number(raw["On Bottom ROP"])
            complete = all(value is not None for value in (rop, wob, rpm, torque, flow))
            if not complete:
                skipped["invalid_numeric"] += 1
            # Rig state is inferred only for screening. A reviewer must verify
            # this classification against source rig operations before qualification.
            advancing = prior_md is not None and md_m > prior_md + 0.0001
            forward = complete and on_bottom is not None and on_bottom > 0 \
                and wob > 0 and rop > 0 and advancing
            samples.append(HistoricalSample(
                wellbore_id=config.wellbore_id,
                source_record_id=f"csv-line:{line_number}", revision=1,
                observed_at=observed, available_at=available, received_at=received,
                md_m=md_m, depth_reference_id=config.depth_reference_id,
                rig_state="forward_drilling" if forward else "unknown",
                quality="good" if complete else "missing",
                rop_m_per_h=rop * FT_TO_M if rop is not None else None,
                wob_kn=wob * KLBF_TO_KN if wob is not None else None,
                rpm=rpm,
                torque_kn_m=torque * KFTLBF_TO_KNM if torque is not None else None,
                flow_in_l_per_min=flow * GPM_TO_LPM if flow is not None else None,
                raw_values={name: raw.get(name) for name in (*REQUIRED, "Memos")},
                source_quality_code="heuristic_rig_state_unreviewed",
            ))
            prior_md = md_m
    if not samples:
        raise ValueError("No rows in selected interval")
    batch = HistoricalBatch(
        schema_version="historical-drilling-parameters-v1",
        dataset_id=config.dataset_id,
        external_id=f"forge-56-32-raw-10s-{digest[:20]}",
        source_sha256=digest, source_kind="csv_export",
        source_reference=SOURCE_URL,
        permission_reference=config.permission_reference,
        source_timezone=config.source_timezone, md_datum=config.md_datum,
        source_units=config.source_units,
        mapping_version="forge-56-32-raw-10s-v1",
        samples=samples,
    )
    report = screen_batch(samples)
    report.update(
        source_sha256=digest,
        selected_interval=[config.start_local.isoformat(), config.end_local.isoformat()],
        input_rows_selected=len(samples), skipped=skipped,
        depth_semantics_reference=config.depth_semantics_reference,
        availability_reference=config.availability_reference,
        unit_reference=config.unit_reference,
        raw_source_url=SOURCE_URL, standardized_unit_source_url=STANDARD_URL,
        labels_created=0, mud_density_supplied=False,
    )
    return batch, report


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare one FORGE 56-32 drilling interval")
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    config = Forge56Config.model_validate_json(args.config.read_text())
    batch, report = prepare(args.csv, config)
    print(json.dumps(report, sort_keys=True))
    if report["decision"] == "stop":
        raise SystemExit(2)
    with args.out.open("x", encoding="utf-8") as stream:
        stream.write(batch.model_dump_json(indent=2))
    print(json.dumps({"batch_path": str(args.out), "state": "prepared_not_staged"}))


if __name__ == "__main__":
    main()
