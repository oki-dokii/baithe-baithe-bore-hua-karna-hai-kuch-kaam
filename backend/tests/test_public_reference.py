import copy
import json

import pytest

from nwis.public_reference import QUESTIONS, REFERENCE, validate


@pytest.fixture
def manifests():
    return json.loads(REFERENCE.read_text()), json.loads(QUESTIONS.read_text())


def test_public_reference_is_provisional_and_structurally_complete(manifests):
    report = validate(*manifests)
    assert report["reports"] == 3
    assert report["annotated_passages"] == 25
    assert report["fixed_questions"] == 18
    assert report["passage_kinds"]["hard_negative"] >= 5
    assert not report["domain_approved"]
    assert not report["api_recall_scored"]
    assert not report["operational_evidence_eligible"]


def test_disputed_nod_511_depth_stays_source_only(manifests):
    reference, questions = manifests
    items = {item["id"]: item for item in reference["items"]}
    reported = items["R002"]
    assert reported["depth"]["value"] == 7733
    assert reported["depth"]["axis"] is None
    assert reported["depth"]["datum"] is None
    assert "disputed" in reported["caveat"]
    assert all(items[item_id]["kind"] == "context" for item_id in ("R023", "R024", "R025"))
    sequence = next(question for question in questions["questions"] if question["id"] == "PQ18")
    assert sequence["answerability"] == "supported_with_conflict"


@pytest.mark.parametrize(
    "change",
    [
        lambda r, q: r["items"][0].update(source_id="unknown"),
        lambda r, q: r["items"][0].update(pdf_page=999),
        lambda r, q: r["items"][1].update(event_type=None),
        lambda r, q: q["questions"][0].update(expected_reference_item_ids=["unknown"]),
        lambda r, q: next(item for item in q["questions"] if item["id"] == "PQ17").update(
            expected_reference_item_ids=["R002"]
        ),
        lambda r, q: r.update(status="domain_approved"),
    ],
)
def test_reference_rejects_invalid_or_overclaimed_cases(manifests, change):
    reference, questions = copy.deepcopy(manifests)
    change(reference, questions)
    with pytest.raises(ValueError):
        validate(reference, questions)
