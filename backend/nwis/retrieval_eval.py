"""Read-only, fixed-question retrieval evaluation; never judges citation truth automatically."""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Literal
from uuid import UUID

from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from nwis.config import get_settings
from nwis.ingestion.contracts import Hazard
from nwis.main import app


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=1, max_length=1000)
    wellbore_id: UUID | None = None
    formation_id: UUID | None = None
    hazard: Hazard | None = None
    min_md_m: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    max_md_m: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    expected_passage_ids: list[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_depth_and_sources(self):
        if self.min_md_m is not None and self.max_md_m is not None:
            if self.max_md_m < self.min_md_m:
                raise ValueError("Depth interval is reversed")
        if len(self.expected_passage_ids) != len(set(self.expected_passage_ids)):
            raise ValueError("Expected passage IDs must be unique")
        return self


class Benchmark(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["retrieval-questions-v1"]
    kind: Literal["synthetic", "public", "private"]
    dataset_id: UUID
    source_reference: str = Field(min_length=1)
    review_reference: str = Field(min_length=1)
    questions: list[Question] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [question.id for question in self.questions]
        if len(ids) != len(set(ids)):
            raise ValueError("Question IDs must be unique")
        return self


def evaluate(benchmark: Benchmark, client, token: str):
    """Score exact approved passage IDs in the top five; emit no question or source text."""
    expected_total = 0
    found_total = 0
    positives = 0
    negatives = 0
    correct_abstentions = 0
    incorrect_abstentions = 0
    false_abstentions = 0
    unexpected_negative_results = 0
    uncited_items = 0
    cases = []
    for case in benchmark.questions:
        body = {
            "dataset_id": str(benchmark.dataset_id),
            "question": case.question,
            "limit": 5,
            "offset": 0,
        }
        for key in ("wellbore_id", "formation_id", "hazard", "min_md_m", "max_md_m"):
            value = getattr(case, key)
            if value is not None:
                body[key] = str(value) if isinstance(value, UUID) else value
        response = client.post(
            "/api/v1/query", json=body, headers={"Authorization": f"Bearer {token}"}
        )
        if response.status_code != 200:
            raise ValueError(f"Question {case.id}: query returned HTTP {response.status_code}")
        result = response.json()
        if result.get("retrieval_mode") != "postgresql_full_text":
            raise ValueError(f"Question {case.id}: unexpected retrieval mode")
        items = result.get("items")
        if not isinstance(items, list) or len(items) > 5:
            raise ValueError(f"Question {case.id}: malformed top-five results")
        found = set()
        for item in items:
            citations = item.get("citations")
            if not isinstance(citations, list) or not citations:
                uncited_items += 1
                continue
            found.update(str(citation.get("passage_id")) for citation in citations)
        expected = {str(passage_id) for passage_id in case.expected_passage_ids}
        matched = len(expected & found)
        if expected:
            positives += 1
            expected_total += len(expected)
            found_total += matched
            if not items:
                false_abstentions += 1
        else:
            negatives += 1
            if not items and result.get("abstention_reason") == "no_approved_supporting_evidence":
                correct_abstentions += 1
            else:
                if not items:
                    incorrect_abstentions += 1
                unexpected_negative_results += len(items)
        cases.append(
            {
                "id": case.id,
                "expected_sources": len(expected),
                "found_sources": matched,
                "returned_items": len(items),
                "abstained": not items,
            }
        )
    digest = hashlib.sha256(benchmark.model_dump_json().encode()).hexdigest()
    return {
        "manifest_sha256": digest,
        "kind": benchmark.kind,
        "dataset_id": str(benchmark.dataset_id),
        "retrieval_mode": "postgresql_full_text",
        "question_count": len(cases),
        "positive_questions": positives,
        "expected_sources": expected_total,
        "found_sources_at_5": found_total,
        "source_recall_at_5": found_total / expected_total if expected_total else None,
        "correct_abstentions": correct_abstentions,
        "incorrect_abstentions": incorrect_abstentions,
        "negative_question_count": negatives,
        "false_abstentions": false_abstentions,
        "unexpected_results_on_negative_questions": unexpected_negative_results,
        "uncited_returned_items": uncited_items,
        "cases": cases,
        "limitations": [
            "Citation presence is not citation correctness or claim entailment; human review is required.",
            "Question and expected-source quality are asserted by the manifest, not verified by this tool.",
            "Full-text retrieval is not semantic retrieval; no generated answer is evaluated.",
        ],
        "gates": {
            "at_least_15_questions": len(cases) >= 15,
            "positive_and_negative_cases": positives > 0 and negatives > 0,
            "real_source": benchmark.kind != "synthetic",
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Score a frozen retrieval question set locally")
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        benchmark = Benchmark.model_validate_json(args.manifest.read_text())
    except ValidationError as exc:
        locations = [".".join(map(str, error["loc"])) for error in exc.errors(include_input=False)]
        print(json.dumps({"invalid_manifest_fields": locations}), file=sys.stderr)
        raise SystemExit(1) from None
    with TestClient(app) as client:
        report = evaluate(benchmark, client, get_settings().viewer_token)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if all(report["gates"].values()) else 2)


if __name__ == "__main__":
    main()
