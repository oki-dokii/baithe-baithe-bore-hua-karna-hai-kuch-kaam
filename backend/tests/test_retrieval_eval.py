from uuid import uuid4

import pytest
from pydantic import ValidationError

from nwis.retrieval_eval import Benchmark, evaluate


class Reply:
    status_code = 200

    def __init__(self, body):
        self.body = body

    def json(self):
        return self.body


class StubClient:
    def __init__(self, passage_id):
        self.passage_id = passage_id
        self.calls = []

    def post(self, path, json, headers):
        self.calls.append((path, json, headers))
        positive = json["question"] == "fluid losses"
        return Reply(
            {
                "retrieval_mode": "postgresql_full_text",
                "items": (
                    [{"citations": [{"passage_id": str(self.passage_id)}]}] if positive else []
                ),
                "abstention_reason": None if positive else "no_approved_supporting_evidence",
            }
        )


def manifest(passage_id, count=15):
    return Benchmark.model_validate(
        {
            "schema_version": "retrieval-questions-v1",
            "kind": "public",
            "dataset_id": str(uuid4()),
            "source_reference": "public source and checksum registry",
            "review_reference": "reviewed question set v1",
            "questions": [
                {
                    "id": f"Q{i:02d}",
                    "question": "fluid losses" if i == 0 else "no supporting material",
                    "expected_passage_ids": [str(passage_id)] if i == 0 else [],
                }
                for i in range(count)
            ],
        }
    )


def test_scores_sources_and_abstentions_without_exposing_question_text():
    passage = uuid4()
    client = StubClient(passage)
    report = evaluate(manifest(passage), client, "test-token")
    assert report["source_recall_at_5"] == 1
    assert report["correct_abstentions"] == 14
    assert report["negative_question_count"] == 14
    assert report["uncited_returned_items"] == 0
    assert all(report["gates"].values())
    assert "fluid losses" not in str(report)
    assert "test-token" not in str(report)
    assert all(call[0] == "/api/v1/query" and call[1]["limit"] == 5 for call in client.calls)


def test_short_synthetic_set_reports_gates_not_a_success_claim():
    passage = uuid4()
    benchmark = manifest(passage, 1).model_copy(update={"kind": "synthetic"})
    report = evaluate(benchmark, StubClient(passage), "test-token")
    assert report["gates"] == {
        "at_least_15_questions": False,
        "positive_and_negative_cases": False,
        "real_source": False,
    }
    assert report["source_recall_at_5"] == 1
    assert report["negative_question_count"] == 0


def test_duplicate_question_and_bad_depth_are_rejected():
    passage = uuid4()
    source = manifest(passage, 2).model_dump(mode="json")
    source["questions"][1]["id"] = "Q00"
    with pytest.raises(ValidationError, match="Question IDs must be unique"):
        Benchmark.model_validate(source)
    source["questions"][1]["id"] = "Q01"
    source["questions"][1]["min_md_m"] = 2100
    source["questions"][1]["max_md_m"] = 2000
    with pytest.raises(ValidationError, match="Depth interval is reversed"):
        Benchmark.model_validate(source)


def test_query_failure_raises_without_echoing_response_or_question():
    class ErrorClient:
        def post(self, *_args, **_kwargs):
            return type("Error", (), {"status_code": 503})()

    with pytest.raises(ValueError, match="HTTP 503") as exc:
        evaluate(manifest(uuid4(), 1), ErrorClient(), "test-token")
    assert "fluid losses" not in str(exc.value)


def test_empty_response_without_explicit_abstention_is_not_counted_correct():
    class MissingReasonClient:
        def post(self, *_args, **_kwargs):
            return Reply({"retrieval_mode": "postgresql_full_text", "items": []})

    benchmark = manifest(uuid4(), 2)
    report = evaluate(benchmark, MissingReasonClient(), "test-token")
    assert report["correct_abstentions"] == 0
    assert report["incorrect_abstentions"] == 1
    assert report["false_abstentions"] == 1
