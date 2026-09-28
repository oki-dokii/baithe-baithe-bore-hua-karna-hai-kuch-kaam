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
