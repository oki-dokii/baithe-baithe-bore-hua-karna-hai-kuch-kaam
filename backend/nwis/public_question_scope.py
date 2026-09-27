"""Keep event retrieval separate from report-fact QA and disputed-source questions."""

import json
from collections import Counter

from nwis.public_reference import QUESTIONS, REFERENCE, ROOT, validate as validate_reference

SCOPE = ROOT / "specs/evaluation/public-retrieval-scope-v1.json"
KINDS = {"event_retrieval", "report_fact_qa", "conflict_blocked"}


def validate(reference: dict, questions: dict, scope: dict) -> dict:
    validate_reference(reference, questions)
    if scope.get("schema_version") != "public-retrieval-scope-v1":
        raise ValueError("Wrong retrieval scope schema")
    if scope.get("status") != "development_diagnostic_not_held_out":
        raise ValueError("Public questions must disclose development use")
    cases = scope.get("cases")
    if not isinstance(cases, list):
        raise ValueError("Scope cases must be an array")
    by_id = {case["id"]: case["scope"] for case in cases}
    questions_by_id = {case["id"]: case for case in questions["questions"]}
    items = {item["id"]: item for item in reference["items"]}
    if len(by_id) != len(cases) or set(by_id) != set(questions_by_id):
        raise ValueError("Scope must classify every question exactly once")
    if set(by_id.values()) - KINDS:
        raise ValueError("Unknown retrieval scope")
    for question_id, kind in by_id.items():
        question = questions_by_id[question_id]
        answerability = question["answerability"]
        expected = question["expected_reference_item_ids"]
        if kind == "conflict_blocked":
            if answerability != "supported_with_conflict":
                raise ValueError(f"Non-conflict question marked blocked: {question_id}")
        elif answerability == "supported_with_conflict":
            raise ValueError(f"Conflict question must stay blocked: {question_id}")
        elif kind == "event_retrieval" and answerability != "no_support":
            if answerability != "supported" or any(
                items[item_id]["kind"] != "observed_event" for item_id in expected
            ):
                raise ValueError(f"Event retrieval cannot cover this report fact: {question_id}")
    return {
        "question_count": len(cases),
        "scope_counts": dict(Counter(by_id.values())),
        "independent_held_out": False,
        "api_benchmark_ready": False,
    }


def main() -> None:
    result = validate(
        json.loads(REFERENCE.read_text()),
        json.loads(QUESTIONS.read_text()),
        json.loads(SCOPE.read_text()),
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
