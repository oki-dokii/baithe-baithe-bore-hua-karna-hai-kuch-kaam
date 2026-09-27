"""Validate public-report reference metadata without publishing or approving evidence."""

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "specs/evaluation/public-report-reference-v1.json"
QUESTIONS = ROOT / "specs/evaluation/public-retrieval-questions-v1.json"
KINDS = {"observed_event", "hard_negative", "action_or_outcome", "context"}
ANSWERABILITY = {"supported", "supported_with_conflict", "contradicted", "no_support"}


def validate(reference: dict, questions: dict) -> dict:
    if reference.get("schema_version") != "public-report-reference-v1":
        raise ValueError("Wrong reference schema")
    if reference.get("status") != "analyst_page_verified_not_domain_approved":
        raise ValueError("Reference must not claim domain approval")
    sources = reference.get("sources")
    items = reference.get("items")
    if not isinstance(sources, list) or not isinstance(items, list):
        raise ValueError("Sources and items must be arrays")
    if len(sources) < 3 or len(items) < 20:
        raise ValueError("Need at least three reports and twenty annotated passages")
    by_source = {source["id"]: source for source in sources}
    if len(by_source) != len(sources):
        raise ValueError("Duplicate source IDs")
    for source in sources:
        if not re.fullmatch(r"[a-f0-9]{64}", source["sha256"]):
            raise ValueError(f"Invalid SHA-256 for {source['id']}")
        if (
            source["pdf_pages"] < 1
            or source["byte_size"] < 1
            or Path(source["local_filename"]).name != source["local_filename"]
        ):
            raise ValueError(f"Invalid PDF identity for {source['id']}")
        if not source["pdf_url"].startswith("https://factpages.sodir.no/"):
            raise ValueError(f"Unrecognized PDF source for {source['id']}")
    ids = [item["id"] for item in items]
    if len(set(ids)) != len(items):
        raise ValueError("Duplicate reference item IDs")
    counts = Counter()
    for item in items:
        source = by_source.get(item["source_id"])
        if source is None or not 1 <= item["pdf_page"] <= source["pdf_pages"]:
            raise ValueError(f"Unknown source or page for {item['id']}")
        if item["kind"] not in KINDS or not item["focus"] or not item["section"]:
            raise ValueError(f"Invalid item label for {item['id']}")
        if item["kind"] == "observed_event" and not item["event_type"]:
            raise ValueError(f"Observed event needs a type: {item['id']}")
        if item["kind"] == "hard_negative" and item["event_type"] is not None:
            raise ValueError(f"Hard negative must not be labeled an event: {item['id']}")
        depth = item["depth"]
        if depth is not None and (depth["value"] < 0 or depth["unit"] not in {"m", "ft"}):
            raise ValueError(f"Invalid source depth for {item['id']}")
        counts[item["kind"]] += 1
    if len({item["source_id"] for item in items}) < 3:
        raise ValueError("Annotations do not span three reports")
    if counts["observed_event"] == 0 or counts["hard_negative"] == 0:
        raise ValueError("Reference needs events and hard negatives")
    if questions.get("schema_version") != "public-retrieval-questions-v1":
        raise ValueError("Wrong question schema")
    if questions.get("status") != "frozen_reference_questions_not_api_scored":
        raise ValueError("Questions must not claim an API score")
    cases = questions.get("questions")
    if not isinstance(cases, list) or len(cases) < 15:
        raise ValueError("Need at least fifteen fixed questions")
    if len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Duplicate question IDs")
    for case in cases:
        if case["answerability"] not in ANSWERABILITY:
            raise ValueError(f"Invalid answerability: {case['id']}")
        if not case["scope"] or set(case["scope"]) - set(by_source):
            raise ValueError(f"Invalid source scope: {case['id']}")
        expected = case["expected_reference_item_ids"]
        if len(expected) != len(set(expected)) or set(expected) - set(ids):
            raise ValueError(f"Invalid expected source IDs: {case['id']}")
        if (case["answerability"] == "no_support") != (len(expected) == 0):
            raise ValueError(f"No-support case has inconsistent expected sources: {case['id']}")
        if any(
            item["source_id"] not in case["scope"]
            for item in items
            if item["id"] in expected
        ):
            raise ValueError(f"Expected item is outside question scope: {case['id']}")
    if not any(case["answerability"] == "no_support" for case in cases):
        raise ValueError("Questions need no-support cases")
    return {
        "reports": len(sources),
        "annotated_passages": len(items),
        "passage_kinds": dict(counts),
        "fixed_questions": len(cases),
        "domain_approved": False,
        "api_recall_scored": False,
        "operational_evidence_eligible": False,
    }


def verify_files(reference: dict, raw_dir: Path) -> dict:
    verified = []
    for source in reference["sources"]:
        path = raw_dir / source["local_filename"]
        if path.stat().st_size != source["byte_size"]:
            raise ValueError(f"Byte-count mismatch: {source['id']}")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != source["sha256"]:
            raise ValueError(f"Checksum mismatch: {source['id']}")
        info = subprocess.check_output(["pdfinfo", str(path)], text=True)
        match = re.search(r"^Pages:\s+(\d+)\s*$", info, re.MULTILINE)
        if not match or int(match[1]) != source["pdf_pages"]:
            raise ValueError(f"Page-count mismatch: {source['id']}")
        verified.append(source["id"])
    return {"local_pdf_identity_verified": verified}


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit provisional public-report references")
    parser.add_argument("--raw-dir", type=Path, help="Check ignored local PDF hashes and pages")
    args = parser.parse_args()
    reference = json.loads(REFERENCE.read_text())
    questions = json.loads(QUESTIONS.read_text())
    result = validate(reference, questions)
    if args.raw_dir:
        result.update(verify_files(reference, args.raw_dir))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
