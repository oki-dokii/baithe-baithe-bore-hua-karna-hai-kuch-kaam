from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from nwis.ingestion.contracts import OnsetReview
from nwis.temporal_qualification import Manifest, Window, audit


BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def row(*, well="W1", split="train", label="positive", **changes):
    result = {
        "sample_id": f"{well}-{label}",
        "physical_well_id": well,
        "wellbore_id": f"{well}-A",
        "split": split,
        "label": label,
        "window_start": BASE,
        "window_end": BASE + timedelta(hours=1),
        "coverage_start": BASE,
        "coverage_end": BASE + timedelta(hours=4),
        "coverage_source": "owned synthetic reviewed interval",
        "coverage_reviewed": True,
        "event_free_reviewed": label == "negative",
        "event_id": f"{well}-event" if label == "positive" else None,
        "onset_earliest": BASE + timedelta(hours=2) if label == "positive" else None,
        "onset_latest": BASE + timedelta(hours=2) if label == "positive" else None,
        "onset_basis": "exact_timelog" if label == "positive" else None,
    }
    return result | changes


def manifest(rows, **changes):
    return Manifest.model_validate(
        {
            "schema_version": "temporal-qualification-v1",
            "source_kind": "synthetic",
            "source_reference": "owned fixture",
            "permission_reference": "owned",
            "hazard": "stuck_pipe",
            "horizon_minutes": 120,
            "domain_reviewed": True,
            "windows": rows,
        }
        | changes
    )


def test_onset_review_requires_bounded_offset_times():
    assert OnsetReview(basis="unspecified").earliest is None
    with pytest.raises(ValidationError):
        OnsetReview(basis="day_only_ddr", earliest=BASE, latest=None)
    with pytest.raises(ValidationError):
        OnsetReview(basis="exact_timelog", earliest=BASE, latest=BASE + timedelta(minutes=1))
    with pytest.raises(ValidationError):
        OnsetReview(basis="shift_report", earliest=BASE.replace(tzinfo=None), latest=BASE)
    with pytest.raises(ValidationError):
        OnsetReview(basis="day_only_ddr", earliest=BASE, latest=BASE + timedelta(hours=2))


def test_pre_event_and_future_horizon_are_both_required():
    valid = audit(manifest([row()]))
    assert "pre_event_cutoff_violated" not in valid["blockers"]
    assert "onset_not_certain_within_horizon" not in valid["blockers"]
    during = audit(manifest([row(onset_earliest=BASE + timedelta(hours=1), onset_latest=BASE + timedelta(hours=1))]))
    assert "pre_event_cutoff_violated" in during["blockers"]
    too_uncertain = audit(manifest([row(onset_basis="day_only_ddr", onset_latest=BASE + timedelta(hours=8))]))
    assert "onset_not_certain_within_horizon" in too_uncertain["blockers"]
    missing_outcome = audit(manifest([row(coverage_end=BASE + timedelta(hours=1, minutes=30))]))
    assert "positive_outcome_coverage_gap" in missing_outcome["blockers"]


def test_negative_needs_reviewed_future_coverage():
    result = audit(manifest([row(label="negative", coverage_end=BASE + timedelta(hours=2))]))
    assert "negative_future_horizon_not_covered" in result["blockers"]
    assert "negative_event_free_review_required" in audit(
        manifest([row(label="negative", event_free_reviewed=False)])
    )["blockers"]
    with pytest.raises(ValidationError):
        Window.model_validate(row(label="negative", event_id="should-not-exist"))
    with pytest.raises(ValidationError):
        Window.model_validate(row(window_end=BASE.replace(tzinfo=None)))


def test_grouped_split_floor_reports_coverage_without_authorizing_training():
    rows = [
        row(well=f"P{i}", split=split)
        for i, split in enumerate(("train", "validation", "test"))
    ] + [
        row(well=f"N{i}", split=split, label="negative")
        for i, split in enumerate(("train", "validation", "test"))
    ]
    result = audit(manifest(rows, source_kind="public"))
    assert result["structural_checks_passed"]
    assert result["positive_physical_wells"] == 3
    assert result["negative_only_physical_wells"] == 3
    assert result["training_authorized"] is False
    result = audit(manifest(rows + [row(well="P0", split="test", label="negative")]))
    assert "physical_well_split_leakage" in result["blockers"]
