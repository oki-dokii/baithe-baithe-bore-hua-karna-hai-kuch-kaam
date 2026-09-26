from nwis.operations import DEPTHS, TRANSITIONS, episode, should_alert


def test_golden_trigger_and_dedup_band():
    assert [should_alert(md, 2130, 2140) for md in DEPTHS] == [False, True, True, True, False]
    assert episode("session", "mud_loss", 2130) == episode("session", "mud_loss", 2140)
    assert episode("other", "mud_loss", 2130) != episode("session", "mud_loss", 2130)
    assert TRANSITIONS["acknowledge"][1] == "ACKNOWLEDGED"
    assert TRANSITIONS["resolve"][1] == "RESOLVED"
