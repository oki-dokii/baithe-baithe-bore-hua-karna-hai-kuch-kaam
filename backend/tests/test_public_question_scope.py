import copy
import json

import pytest

from nwis.public_question_scope import SCOPE, validate
from nwis.public_reference import QUESTIONS, REFERENCE


def manifests():
    return json.loads(REFERENCE.read_text()), json.loads(QUESTIONS.read_text()), json.loads(SCOPE.read_text())


def test_scope_is_complete_and_not_called_held_out():
    report = validate(*manifests())
    assert report["question_count"] == 18
    assert report["scope_counts"] == {
        "conflict_blocked": 2,
        "report_fact_qa": 10,
        "event_retrieval": 6,
    }
    assert not report["independent_held_out"]
    assert not report["api_benchmark_ready"]


@pytest.mark.parametrize(
    "change",
    [
        lambda s: s["cases"].pop(),
        lambda s: s["cases"][0].update(scope="event_retrieval"),
        lambda s: next(c for c in s["cases"] if c["id"] == "PQ04").update(scope="event_retrieval"),
        lambda s: s.update(status="independent_held_out"),
    ],
)
def test_scope_rejects_missing_conflicted_or_overclaimed_cases(change):
    reference, questions, scope = manifests()
    changed = copy.deepcopy(scope)
    change(changed)
    with pytest.raises(ValueError):
        validate(reference, questions, changed)
