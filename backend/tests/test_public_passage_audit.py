import json
from uuid import uuid4

from nwis.public_passage_audit import audit
from nwis.public_reference import QUESTIONS, REFERENCE


class Rows:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class StubConnection:
    def __init__(self, document_sha, page, approved_count):
        self.document_sha = document_sha
        self.page = page
        self.approved_count = approved_count
        self.document_id = uuid4()
        self.passage_id = uuid4()

    def execute(self, query, params):
        if "FROM source_document" in query:
            return Rows(
                [{"id": self.document_id, "page_count": 38, "ingest_status": "complete"}]
                if params[1] == self.document_sha
                else []
            )
        if "FROM extracted_passage" in query:
            if params[1] == self.document_id and params[2] == self.page:
                return Rows(
                    [{
                        "passage_id": self.passage_id,
                        "text_version": 1,
                        "approved_matching_event_count": self.approved_count
                        if params[0] == "mud_loss" else 0,
                    }]
                )
            return Rows([])
        raise AssertionError("Unexpected read-only query")


def test_audit_reports_candidates_without_claiming_approval_or_scoring():
    reference = json.loads(REFERENCE.read_text())
    questions = json.loads(QUESTIONS.read_text())
    source = next(source for source in reference["sources"] if source["id"] == "NOD-399")
    conn = StubConnection(source["sha256"], 23, 1)
    report = audit(reference, questions, uuid4(), conn)
    items = {item["reference_item_id"]: item for item in report["reference_items"]}
    assert len(items) == 25
    assert items["R009"]["state"] == "claim_level_review_required"
    assert items["R009"]["page_candidates"][0]["passage_id"] == str(conn.passage_id)
    assert items["R008"]["state"] == "not_event_indexed"
    assert items["R002"]["state"] == "disputed_depth_blocked"
    assert items["R015"]["state"] == "document_missing"
    assert not report["api_benchmark_ready"]
    assert source["local_filename"] not in str(report)
    assert "Lost circulation at 1305 m" not in str(report)


def test_page_without_approved_matching_event_is_not_mappable():
    reference = json.loads(REFERENCE.read_text())
    questions = json.loads(QUESTIONS.read_text())
    source = next(source for source in reference["sources"] if source["id"] == "NOD-399")
    report = audit(reference, questions, uuid4(), StubConnection(source["sha256"], 23, 0))
    item = next(item for item in report["reference_items"] if item["reference_item_id"] == "R009")
    assert item["state"] == "no_approved_matching_event"
