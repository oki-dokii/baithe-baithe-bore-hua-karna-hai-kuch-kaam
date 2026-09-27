"""Read-only bridge from frozen public reference pages to local passage candidates.

Page co-location is not claim-level review. This tool deliberately cannot approve
events, create a retrieval benchmark, or normalize a disputed depth.
"""

import argparse
import json
from collections import Counter
from uuid import UUID

from nwis.db import connection
from nwis.public_reference import QUESTIONS, REFERENCE, validate


def audit(reference: dict, questions: dict, dataset_id: UUID, conn) -> dict:
    validate(reference, questions)
    documents = {}
    for source in reference["sources"]:
        document = conn.execute(
            """SELECT id,page_count,ingest_status FROM source_document
            WHERE dataset_id=%s AND sha256=%s""",
            (dataset_id, source["sha256"]),
        ).fetchone()
        documents[source["id"]] = document

    items = []
    for item in reference["items"]:
        document = documents[item["source_id"]]
        pages = []
        drafts = []
        if document:
            pages = conn.execute(
                """SELECT p.id AS passage_id,p.text_version,
                count(DISTINCT e.id) FILTER (WHERE e.review_state='approved'
                  AND e.event_type=%s) AS approved_matching_event_count
                FROM extracted_passage p
                LEFT JOIN event_passage ep ON ep.passage_id=p.id
                LEFT JOIN drilling_event e ON e.id=ep.event_id
                WHERE p.document_id=%s AND p.page_number=%s
                GROUP BY p.id,p.text_version ORDER BY p.text_version DESC,p.id""",
                (item["event_type"], document["id"], item["pdf_page"]),
            ).fetchall()
            if item["kind"] == "observed_event":
                drafts = conn.execute(
                    """SELECT c.id,c.state FROM document_event_draft c
                    JOIN extracted_passage p ON p.id=c.passage_id
                    WHERE c.document_id=%s AND p.page_number=%s
                      AND c.current_fields->>'event_type'=%s
                    ORDER BY c.created_at,c.id""",
                    (document["id"], item["pdf_page"], item["event_type"]),
                ).fetchall()
        # One extracted passage is currently a whole page. Even an approved
        # event on that page does not establish which reference item it proves.
        if item["id"] == "R002":
            state = "disputed_depth_blocked"
        elif item["kind"] != "observed_event":
            state = "not_event_indexed"
        elif not document:
            state = "document_missing"
        elif not pages:
            state = "page_missing"
        elif any(row["approved_matching_event_count"] for row in pages):
            state = "claim_level_review_required"
        elif drafts:
            state = "draft_review_required"
        else:
            state = "no_matching_draft"
        items.append(
            {
                "reference_item_id": item["id"],
                "source_id": item["source_id"],
                "pdf_page": item["pdf_page"],
                "kind": item["kind"],
                "state": state,
                "draft_candidates": [
                    {"draft_id": str(row["id"]), "state": row["state"]} for row in drafts
                ],
                "page_candidates": [
                    {
                        "passage_id": str(row["passage_id"]),
                        "text_version": row["text_version"],
                        "approved_matching_event_count": row["approved_matching_event_count"],
                    }
                    for row in pages
                ],
            }
        )
    counts = Counter(item["state"] for item in items)
    return {
        "dataset_id": str(dataset_id),
        "source_documents": {
            source_id: {
                "present": bool(document),
                "page_count": document["page_count"] if document else None,
                "ingest_status": document["ingest_status"] if document else None,
            }
            for source_id, document in documents.items()
        },
        "reference_items": items,
        "state_counts": dict(counts),
        "api_benchmark_ready": False,
        "reason": "Independent claim-level mapping, domain review and benchmark scope are still required",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit local public-report passage candidates")
    parser.add_argument("--dataset-id", type=UUID, required=True)
    args = parser.parse_args()
    reference = json.loads(REFERENCE.read_text())
    questions = json.loads(QUESTIONS.read_text())
    with connection() as conn:
        result = audit(reference, questions, args.dataset_id, conn)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
