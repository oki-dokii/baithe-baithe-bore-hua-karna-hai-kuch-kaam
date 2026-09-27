from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from nwis.mud_loss_adapter import AdapterError, SourceBundle, build_manifest
from nwis.prediction import audit

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def bundle(*, positive=False):
    data = {
        "schema_version": "mud-loss-adapter-input-v1",
        "kind": "synthetic",
        "source_reference": "owned synthetic adapter fixture",
        "source_sha256": "a" * 64,
        "permission_reference": "owned fixture",
        "domain_reviewed": False,
        "anchors": [
            {
                "sample_id": "anchor-a",
                "physical_well_id": "well-a",
                "wellbore_id": "bore-a",
                "split": "train",
                "observed_at": T0,
                "available_at": T0,
                "md_m": 1000,
                "quality": "good",
                "rig_state": "forward_drilling",
                "source_record_id": "sensor-1",
                "features": {
                    "rop_m_per_h": 10,
                    "wob_kn": 40,
                    "rpm": 90,
                    "torque_kn_m": 8,
                    "flow_in_l_per_min": 1000,
                },
            }
        ],
        "mud_density": [
            {
                "wellbore_id": "bore-a",
                "source_record_id": "mud-program-page-1",
                "source_kind": "reviewed_mud_program",
                "recorded_at": T0 - timedelta(days=1),
                "effective_from": T0 - timedelta(days=1),
                "effective_until": None,
                "top_md_m": 900,
                "base_md_m": 1200,
                "mud_density_kg_per_m3": 1200,
                "reviewed": True,
            }
        ],
        "coverage": [
            {
                "wellbore_id": "bore-a",
                "source_reference": "reviewed-coverage-1",
                "top_md_m": 900,
                "base_md_m": 1100,
                "from_time": T0 - timedelta(hours=1),
                "observed_through_at": T0 + timedelta(hours=2),
                "reviewed": True,
                "event_free_reviewed": not positive,
            }
        ],
        "losses": [
            {
                "event_id": "event-1",
                "wellbore_id": "bore-a",
                "onset_md_m": 1050,
                "onset_earliest": T0 + timedelta(minutes=30),
                "onset_latest": T0 + timedelta(minutes=30),
                "onset_basis": "exact_timelog",
                "event_reviewed": True,
                "source_passage_id": "page-1",
                "depth_datum_reviewed": True,
            }
        ]
        if positive
        else [],
    }
    return data


def test_builds_only_from_explicit_reviewed_sources():
    positive = build_manifest(SourceBundle.model_validate(bundle(positive=True)))
    assert positive.windows[0].label == 1
    assert positive.windows[0].features["mud_density_kg_per_m3"] == 1200
    assert "reviewed_event:event-1" in positive.windows[0].label_source
    assert positive.kind == "synthetic"
    assert "synthetic_only_not_real_validation" in audit(positive)["blockers"]
    assert audit(positive)["training_authorized"] is False
    negative = build_manifest(SourceBundle.model_validate(bundle()))
    assert negative.windows[0].label == 0
    assert negative.windows[0].label_source.startswith("reviewed_event_free_coverage:")


@pytest.mark.parametrize(
    "change,code",
    [
        (lambda b: b["mud_density"].clear(), "reviewed_pre_anchor_mud_density_missing"),
        (
            lambda b: b["mud_density"].append(deepcopy(b["mud_density"][0])),
            "overlapping_mud_density_records",
        ),
        (
            lambda b: b["mud_density"][0].update(recorded_at=T0 + timedelta(minutes=1)),
            "reviewed_pre_anchor_mud_density_missing",
        ),
        (lambda b: b["coverage"][0].update(base_md_m=1099), "reviewed_future_coverage_missing"),
        (
            lambda b: b["coverage"][0].update(event_free_reviewed=False),
            "negative_event_free_review_missing",
        ),
    ],
)
def test_negative_window_rejects_missing_or_ambiguous_evidence(change, code):
    source = bundle()
    change(source)
    with pytest.raises(AdapterError, match=code):
        build_manifest(SourceBundle.model_validate(source))


@pytest.mark.parametrize(
    "change,code",
    [
        (
            lambda b: b["losses"][0].update(onset_earliest=T0, onset_latest=T0),
            "positive_feature_time_leakage_or_uncertain_onset",
        ),
        (
            lambda b: b["losses"][0].update(
                onset_earliest=None, onset_latest=None, onset_basis="unspecified"
            ),
            "timed_loss_onset_missing",
        ),
        (lambda b: b["losses"][0].update(event_reviewed=False), "loss_event_review_missing"),
        (
            lambda b: b["coverage"][0].update(event_free_reviewed=True),
            "coverage_conflicts_with_loss_event",
        ),
    ],
)
def test_positive_window_rejects_weak_or_conflicting_event(change, code):
    source = bundle(positive=True)
    change(source)
    with pytest.raises(AdapterError, match=code):
        build_manifest(SourceBundle.model_validate(source))


def test_noncanonical_or_timezone_naive_inputs_fail_validation():
    source = bundle()
    source["anchors"][0]["features"].pop("wob_kn")
    with pytest.raises(ValidationError):
        SourceBundle.model_validate(source)
    source = bundle()
    source["anchors"][0]["observed_at"] = T0.replace(tzinfo=None)
    with pytest.raises(ValidationError):
        SourceBundle.model_validate(source)
    source = bundle()
    source["anchors"][0]["available_at"] = T0 - timedelta(seconds=1)
    with pytest.raises(ValidationError):
        SourceBundle.model_validate(source)
