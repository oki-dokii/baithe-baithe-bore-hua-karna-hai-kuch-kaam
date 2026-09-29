"""Unit tests for NWIS real calibrated Hazard ML Model."""

from nwis.hazard_model import (
    FEATURES,
    generate_drilling_dataset,
    get_active_model,
    predict_hazard,
    train_and_export_model,
)


def test_generate_drilling_dataset_disjoint_wells():
    train_set, val_set, test_set = generate_drilling_dataset()
    assert len(train_set) > 0
    assert len(val_set) > 0
    assert len(test_set) > 0

    train_wells = {s["physical_well_id"] for s in train_set}
    val_wells = {s["physical_well_id"] for s in val_set}
    test_wells = {s["physical_well_id"] for s in test_set}

    # Strict physical well disjointness
    assert len(train_wells & val_wells) == 0
    assert len(train_wells & test_wells) == 0
    assert len(val_wells & test_wells) == 0


def test_trained_model_metrics():
    model = train_and_export_model()
    assert model["model_version"] == "mud-loss-detector-v1.2"
    assert model["hazard"] == "mud_loss"
    assert model["horizon_m"] == 100
    assert model["threshold"] > 0.0

    test_metrics = model["metrics"]["test"]
    assert test_metrics["roc_auc"] >= 0.80
    assert 0.0 <= test_metrics["brier_score"] <= 0.25
    assert len(model["feature_importance"]) == len(FEATURES)


def test_predict_hazard_high_vs_low_risk():
    # Pre-loss signature: drilling break, high torque, high flow, lower mud density
    high_risk = predict_hazard({
        "rop_m_per_h": 19.0,
        "wob_kn": 52.0,
        "rpm": 125.0,
        "torque_kn_m": 12.0,
        "flow_in_l_per_min": 1950.0,
        "mud_density_kg_per_m3": 1140.0,
    })
    assert high_risk["probability"] > 0.70
    assert high_risk["risk_level"] in ("HIGH", "CRITICAL")
    assert high_risk["is_alert"] is True
    assert len(high_risk["feature_contributions"]) == len(FEATURES)

    # Normal baseline parameters
    low_risk = predict_hazard({
        "rop_m_per_h": 6.0,
        "wob_kn": 28.0,
        "rpm": 82.0,
        "torque_kn_m": 4.5,
        "flow_in_l_per_min": 1450.0,
        "mud_density_kg_per_m3": 1250.0,
    })
    assert low_risk["probability"] < 0.25
    assert low_risk["risk_level"] == "LOW"
    assert low_risk["is_alert"] is False


def test_get_active_model_cached():
    model = get_active_model()
    assert model["model_version"] == "mud-loss-detector-v1.2"
    cached = get_active_model()
    assert cached is model

