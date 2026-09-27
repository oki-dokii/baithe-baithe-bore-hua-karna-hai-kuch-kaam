from pathlib import Path

import pytest

from nwis.prediction import DatasetManifest, audit, model_card
from nwis.train_mud_loss import (
    STATE,
    TrainingRefused,
    average_precision,
    demo_manifest,
    roc_auc,
    train,
)


def test_demo_pipeline_is_deterministic_and_never_deployed():
    manifest = demo_manifest()
    report = audit(manifest)
    assert set(report["blockers"]) == {
        "synthetic_only_not_real_validation",
        "domain_review_required",
    }
    assert not report["training_authorized"]
    first, card = train(manifest)
    second, again = train(manifest)
    assert first == second and card == again
    assert card["state"] == STATE
    assert card["source_kind"] == "synthetic"
    assert card["training_authorized"] is False
    assert card["operationally_validated"] is False
    assert card["deployed"] is False
    assert card["calibrated"] is False
    assert card["test"]["prevalence_roc_auc"] == 0.5
    assert card["test"]["prevalence_average_precision"] == 0.5
    assert 0 <= card["test"]["model_brier"] <= 1
    assert sum(bin_["n"] for bin_ in card["test"]["reliability_bins"]) == 8
    assert model_card()["reason"] == "model_not_available"
    assert model_card()["model_version"] is None


def test_test_labels_never_fit_model_or_select_threshold():
    original = demo_manifest()
    original_artifact, original_card = train(original)
    altered = original.model_copy(deep=True)
    test_positive = next(w for w in altered.windows if w.split == "test" and w.label == 1)
    test_positive.next_loss_md_m = None
    altered_artifact, altered_card = train(altered)
    for key in ("means", "scales", "weights", "intercept", "threshold"):
        assert altered_artifact[key] == original_artifact[key]
    assert altered_card["test"]["model_brier"] != original_card["test"]["model_brier"]
    feature_shift = original.model_copy(deep=True)
    for window in feature_shift.windows:
        if window.split == "test":
            window.features["torque_kn_m"] *= 100
    shifted_artifact, _ = train(feature_shift)
    for key in ("means", "scales", "weights", "intercept", "threshold"):
        assert shifted_artifact[key] == original_artifact[key]


def test_rejects_real_manifests_and_group_leakage():
    real = DatasetManifest.model_validate({**demo_manifest().model_dump(), "kind": "public"})
    with pytest.raises(TrainingRefused, match="real_training_not_authorized"):
        train(real)
    leaked = demo_manifest().model_copy(deep=True)
    train_well = next(w.physical_well_id for w in leaked.windows if w.split == "train")
    for window in leaked.windows:
        if window.split == "test":
            window.physical_well_id = train_well
            break
    with pytest.raises(TrainingRefused, match="manifest_fails_software_structure_gate"):
        train(leaked)


def test_tied_baselines_have_honest_ranking_metrics():
    labels = [0, 1, 0, 1]
    scores = [0.5] * 4
    assert roc_auc(labels, scores) == 0.5
    assert average_precision(labels, scores) == 0.5


def test_demo_manifest_can_roundtrip_through_window_schema(tmp_path: Path):
    source = tmp_path / "manifest.json"
    source.write_text(demo_manifest().model_dump_json(indent=2))
    loaded = DatasetManifest.model_validate_json(source.read_text())
    assert train(loaded) == train(demo_manifest())
