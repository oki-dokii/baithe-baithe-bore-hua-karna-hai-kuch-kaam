from nwis.operations import DEPTHS, TRANSITIONS, episode, priority_class, should_alert


def test_golden_trigger_and_dedup_band():
    assert [should_alert(md, 2130, 2140) for md in DEPTHS] == [False, True, True, True, False]
    assert episode("session", "mud_loss", 2130) == episode("session", "mud_loss", 2140)
    assert episode("other", "mud_loss", 2130) != episode("session", "mud_loss", 2130)
    assert TRANSITIONS["acknowledge"][1] == "ACKNOWLEDGED"
    assert TRANSITIONS["resolve"][1] == "RESOLVED"


def test_budget_only_classifies_explicit_low_non_well_control_cases():
    def support(hazard, severity):
        return [({"event_type": hazard, "severity": severity}, None, None, None)]

    assert priority_class(support("torque_spike", "low")) == "advisory"
    assert priority_class(support("mud_loss", "low")) == "safety_critical"
    assert priority_class(support("torque_spike", None)) == "safety_critical"
    assert priority_class(support("kick", "high")) == "safety_critical"


def test_hazard_model_predict_hazard_output():
    from nwis.hazard_model import predict_hazard
    pred = predict_hazard({
        "rop_m_per_h": 16.5,
        "wob_kn": 48.0,
        "rpm": 115.0,
        "torque_kn_m": 11.2,
        "flow_in_l_per_min": 1920.0,
        "mud_density_kg_per_m3": 1145.0,
    })
    assert pred["hazard"] == "mud_loss"
    assert "probability" in pred
    assert pred["risk_level"] in ("HIGH", "CRITICAL")
    assert pred["is_alert"] is True
    assert "recommended_action" in pred
    assert len(pred["feature_contributions"]) == 6
