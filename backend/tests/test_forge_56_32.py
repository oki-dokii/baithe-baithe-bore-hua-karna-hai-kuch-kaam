import csv
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from nwis.forge_56_32 import Forge56Config, UNITS, prepare


def config(**changes):
    return Forge56Config.model_validate({
        "schema_version": "forge-56-32-raw-10s-v2",
        "dataset_id": uuid4(), "wellbore_id": uuid4(), "depth_reference_id": uuid4(),
        "permission_reference": "owned fixture terms", "source_timezone": "UTC",
        "md_datum": "KB", "depth_semantics_reference": "fixture reviewer assertion",
        "availability_lag_seconds": 10,
        "availability_reference": "fixture time semantics",
        "unit_reference": "fixture matching standardized header",
        "receipt_at": "2026-01-01T00:00:00Z",
        "source_units": UNITS,
        "start_local": "2021-02-08T00:00:00",
        "end_local": "2021-02-08T00:20:00",
    } | changes)


def write_fixture(path, *, flat=False):
    headers = ["Hole Depth", "Weight on Bit", "Rotary RPM", "Convertible Torque",
               "Flow", "Rate Of Penetration", "YYYY/MM/DD", "HH:MM:SS",
               "On Bottom ROP", "Memos"]
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers)
        writer.writeheader()
        for i in range(50):
            when = datetime(2021, 2, 8) + timedelta(seconds=i * 20)
            writer.writerow({
                "Hole Depth": 1000 if flat else 1000 + 2 * i,
                "Weight on Bit": 0 if flat else 5 + i % 5,
                "Rotary RPM": 0 if flat else 80 + i % 4,
                "Convertible Torque": 0 if flat else 2 + i % 3,
                "Flow": 0 if flat else 200,
                "Rate Of Penetration": 0 if flat else 10 + i % 5,
                "YYYY/MM/DD": when.strftime("%Y/%m/%d"),
                "HH:MM:SS": when.strftime("%H:%M:%S"),
                "On Bottom ROP": 0 if flat else 10,
                "Memos": "lost circulation?" if i == 30 else "",
            })


def test_forge_mapper_converts_units_and_preserves_unreviewed_state(tmp_path):
    path = tmp_path / "56-32.csv"
    write_fixture(path)
    batch, report = prepare(path, config())
    assert report["decision"] == "screen_passed_needs_review"
    assert len(batch.samples) == 50
    assert batch.samples[0].md_m == pytest.approx(304.8)
    assert batch.samples[0].wob_kn == pytest.approx(22.241108)
    assert batch.samples[0].torque_kn_m == pytest.approx(2.7116359)
    assert batch.samples[0].flow_in_l_per_min == pytest.approx(757.0823568)
    assert batch.samples[1].available_at > batch.samples[1].observed_at
    assert batch.samples[1].rig_state == "forward_drilling"
    assert batch.samples[30].raw_values["Memos"] == "lost circulation?"
    assert report["labels_created"] == 0
    assert not report["mud_density_supplied"]
    repeated, _ = prepare(path, config(
        dataset_id=batch.dataset_id, wellbore_id=batch.samples[0].wellbore_id,
        depth_reference_id=batch.samples[0].depth_reference_id,
    ))
    assert repeated.samples[0].model_dump(mode="json") == batch.samples[0].model_dump(mode="json")
    assert batch.mapping_evidence.availability_policy == "fixed_lag_seconds:10"
    assert batch.mapping_evidence.receipt_at == batch.samples[0].received_at


def test_forge_mapper_stops_flat_slice_and_rejects_unverified_units(tmp_path):
    path = tmp_path / "56-32.csv"
    write_fixture(path, flat=True)
    _, report = prepare(path, config())
    assert report["decision"] == "stop"
    assert "no_sustained_measured_depth_advance" in report["wellbores"][0]["blockers"]
    with pytest.raises(ValidationError):
        config(source_units=UNITS | {"Flow": "L/min"})


def test_forge_mapper_refuses_wrong_header(tmp_path):
    path = tmp_path / "wrong.csv"
    path.write_text("Time,ROP\n2021-02-08,10\n")
    with pytest.raises(ValueError, match="header mismatch"):
        prepare(path, config())
