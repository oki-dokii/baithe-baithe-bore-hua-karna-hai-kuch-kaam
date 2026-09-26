import pytest
from pydantic import ValidationError

from nwis.prediction import DatasetManifest, FEATURES, Window, audit, model_card


def window(**overrides):
    return {
        "sample_id": "sample-1",
        "physical_well_id": "well-1",
        "wellbore_id": "bore-1",
        "split": "train",
        "anchor_md_m": 1000,
        "feature_end_md_m": 1000,
        "observed_through_md_m": 1100,
        "next_loss_md_m": 1100,
        "label_reviewed": True,
        "label_source": "owned synthetic onset",
        "features": dict.fromkeys(FEATURES, 1.0),
        **overrides,
    }


def manifest(rows, **overrides):
    return DatasetManifest.model_validate(
        {
            "schema_version": "mud-loss-windows-v1",
            "kind": "synthetic",
            "source_reference": "owned test fixture",
            "source_sha256": "a" * 64,
            "permission_reference": "owned",
            "domain_reviewed": True,
            "windows": rows,
            **overrides,
        }
    )


@pytest.mark.parametrize(
    "change",
    [
        {"feature_end_md_m": 1001},
        {"observed_through_md_m": 1099},
        {"next_loss_md_m": 1000},
        {"next_loss_md_m": 1101},
        {"features": {**dict.fromkeys(FEATURES, 1), "outcome": 1}},
        {"features": dict.fromkeys(FEATURES, float("nan"))},
        {"features": dict.fromkeys(FEATURES, -1)},
    ],
)
def test_invalid_window(change):
    with pytest.raises(ValidationError):
        Window.model_validate(window(**change))


def test_horizon_boundary():
    assert Window.model_validate(window()).label == 1
    assert Window.model_validate(window(next_loss_md_m=None)).label == 0
    assert Window.model_validate(window(next_loss_md_m=1101, observed_through_md_m=1200)).label == 0


def test_leakage_and_duplicates():
    rows = [window(), window(sample_id="s2", wellbore_id="sidetrack", split="test"), window()]
    report = audit(manifest(rows))
    assert "physical_well_split_leakage" in report["blockers"]
    assert "duplicate_samples" in report["blockers"]
    assert "synthetic_only_not_real_validation" in report["blockers"]
    assert report["training_authorized"] is False


def test_structural_floor_never_authorizes_training():
    rows = [
        window(
            sample_id=f"{split}-{i}",
            physical_well_id=f"{split}-{i}",
            wellbore_id=f"{split}-{i}",
            split=split,
            next_loss_md_m=1100 if i else None,
        )
        for split in ("train", "validation", "test")
        for i in range(2)
    ]
    data = manifest(rows, kind="public")
    report = audit(data)
    assert report["structural_checks_passed"]
    assert not report["training_authorized"]
    assert not report["operationally_validated"]
    assert audit(data)["manifest_sha256"] == report["manifest_sha256"]
    assert model_card()["score"] is None
    assert model_card()["metrics"] is None


def test_unreviewed_and_parent_mismatch():
    result = audit(
        manifest(
            [
                window(),
                window(
                    sample_id="s2",
                    anchor_md_m=1200,
                    feature_end_md_m=1200,
                    observed_through_md_m=1300,
                    next_loss_md_m=None,
                    physical_well_id="other",
                    label_reviewed=False,
                ),
            ],
            domain_reviewed=False,
        )
    )
    assert {"inconsistent_wellbore_parent", "unreviewed_labels", "domain_review_required"} <= set(
        result["blockers"]
    )
