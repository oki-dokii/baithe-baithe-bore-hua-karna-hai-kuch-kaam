import pytest

from nwis.witsml_messages import extract


def test_message_time_is_not_promoted_to_event_onset(tmp_path):
    path = tmp_path / "messages.xml"
    path.write_text("""<messages xmlns="http://www.witsml.org/schemas/1series"
        version="1.4.1.1"><message uid="m1" uidWell="w1" uidWellbore="b1">
        <dTim>2021-02-08T01:02:03Z</dTim><md uom="ft">1500</md>
        <typeMessage>information</typeMessage>
        <messageText>No mud loss observed; continue drilling.</messageText>
        </message></messages>""")
    result = extract(path)
    assert result["candidate_count"] == 1
    assert result["approved_event_count"] == 0
    row = result["messages"][0]
    assert row["message_at"] == "2021-02-08T01:02:03Z"
    assert row["onset_basis"] == "unestablished"
    assert row["review_state"] == "unreviewed_message_not_event"
    assert row["source_wellbore_uid"] == "b1"
    assert row["message_md_unit"] == "ft"


def test_message_parser_rejects_dtd_and_unzoned_time(tmp_path):
    path = tmp_path / "messages.xml"
    path.write_text("<!DOCTYPE messages [<!ENTITY x 'bad'>]><messages/>")
    with pytest.raises(ValueError, match="DTD"):
        extract(path)
    path.write_text("""<messages xmlns="http://www.witsml.org/schemas/1series"
      version="1.4.1.1"><message uid="m"><dTim>2021-02-08T01:02:03</dTim>
      <messageText>kick</messageText></message></messages>""")
    with pytest.raises(ValueError, match="UTC offset"):
        extract(path)
