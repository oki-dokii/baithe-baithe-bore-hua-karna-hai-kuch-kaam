"""Stage pinned NOD PDFs in an isolated, unreviewed retrieval benchmark database.

This uses the normal document upload and ingestion worker, but never approves a
draft or makes the placeholder well locations eligible for map/alert claims.
"""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

from fastapi.testclient import TestClient

from nwis.config import get_settings
from nwis.db import connection
from nwis.ingestion.jobs import tick
from nwis.main import app
from nwis.public_reference import QUESTIONS, REFERENCE, validate, verify_files
from nwis.seed import stable_id

DATASET_EXTERNAL_ID = "nod-public-report-benchmark-v1"
DATASET_ID = stable_id("dataset", DATASET_EXTERNAL_ID)
DATABASE_NAME = "nwis_public_benchmark"
SOURCE_ORDER = ("NOD-399", "NOD-511", "NOD-6599")


def guard() -> None:
    settings = get_settings()
    parsed = urlparse(settings.database_url)
    if settings.environment == "production" or settings.extraction_provider != "local_rules":
        raise ValueError("Public benchmark staging requires non-production local-rules mode")
    if parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.path != f"/{DATABASE_NAME}":
        raise ValueError(f"Use the isolated local {DATABASE_NAME} database")
    if settings.storage_root.resolve() != (Path(__file__).resolve().parents[1] / "storage/public-benchmark").resolve():
        raise ValueError("Use backend/storage/public-benchmark for ignored document storage")
    if settings.document_max_pages < 166:
        raise ValueError("Set NWIS_DOCUMENT_MAX_PAGES=200 for these pinned reports")


def prepare(reference: dict, questions: dict, raw_dir: Path) -> dict:
    guard()
    validate(reference, questions)
    verify_files(reference, raw_dir)
    version = hashlib.sha256(REFERENCE.read_bytes()).hexdigest()
    by_id = {source["id"]: source for source in reference["sources"]}
    if set(by_id) != set(SOURCE_ORDER):
        raise ValueError("Unexpected public reference source set")
    with connection() as conn:
        datasets = conn.execute("SELECT id,kind,version,qualification_status FROM dataset").fetchall()
        if any(row["id"] != DATASET_ID for row in datasets):
            raise ValueError("Benchmark database already contains another dataset")
        if datasets and (
            datasets[0]["kind"] != "public"
            or datasets[0]["version"] != version
            or datasets[0]["qualification_status"] != "staged_unreviewed"
        ):
            raise ValueError("Existing benchmark dataset does not match pinned reference")
        if not datasets:
            conn.execute(
                """INSERT INTO dataset(id,external_id,name,kind,source_url,version,
                   license_reference,qualification_status)
                   VALUES(%s,%s,%s,'public',%s,%s,%s,'staged_unreviewed')""",
                (
                    DATASET_ID,
                    DATASET_EXTERNAL_ID,
                    "NOD public reports — retrieval benchmark staging only",
                    "https://factpages.sodir.no/",
                    version,
                    "https://www.sodir.no/en/about-us/use-of-content/",
                ),
            )
        for source_id in SOURCE_ORDER:
            source = by_id[source_id]
            well_id = stable_id("well", f"{DATASET_EXTERNAL_ID}:{source_id}")
            bore_id = stable_id("wellbore", f"{DATASET_EXTERNAL_ID}:{source_id}")
            existing = conn.execute(
                "SELECT id FROM well WHERE dataset_id=%s AND external_id=%s",
                (DATASET_ID, source_id),
            ).fetchone()
            if not existing:
                # The schema requires a point; (0,0) is a conspicuous sentinel,
                # not a Norwegian coordinate. This database is never the map demo.
                conn.execute(
                    """INSERT INTO well(id,dataset_id,external_id,name,basin_name,status,
                       surface_point) VALUES(%s,%s,%s,%s,'NORTH SEA','benchmark_unlocated',
                       ST_SetSRID(ST_MakePoint(0,0),4326)::geography)""",
                    (well_id, DATASET_ID, source_id, source["wellbore"]),
                )
                conn.execute(
                    "INSERT INTO wellbore(id,well_id,external_id,status) VALUES(%s,%s,%s,'benchmark_unlocated')",
                    (bore_id, well_id, source_id),
                )
            elif existing["id"] != well_id:
                raise ValueError(f"Unexpected well identity for {source_id}")
        approved = conn.execute(
            "SELECT count(*) AS n FROM drilling_event WHERE review_state='approved'"
        ).fetchone()["n"]
        if approved:
            raise ValueError("Benchmark staging database contains approved events")

    uploaded = []
    with TestClient(app) as client:
        for source_id in SOURCE_ORDER:
            source = by_id[source_id]
            path = raw_dir / source["local_filename"]
            bore_id = stable_id("wellbore", f"{DATASET_EXTERNAL_ID}:{source_id}")
            response = client.post(
                "/api/v1/documents",
                data={"dataset_id": str(DATASET_ID), "wellbore_id": str(bore_id)},
                files={"file": (source["local_filename"], path.read_bytes(), "application/pdf")},
                headers={
                    "Authorization": f"Bearer {get_settings().reviewer_token}",
                    "Idempotency-Key": str(stable_id("public-upload", source_id)),
                },
            )
            if response.status_code != 202:
                raise RuntimeError(f"Upload failed for {source_id}: HTTP {response.status_code}")
            uploaded.append({"source_id": source_id, "document_id": response.json()["id"]})
    return {"dataset_id": str(DATASET_ID), "uploaded": uploaded, "approved_events": 0}


def process_one() -> dict:
    guard()
    with connection() as conn:
        datasets = conn.execute("SELECT id,qualification_status FROM dataset").fetchall()
        if len(datasets) != 1 or datasets[0] != {
            "id": DATASET_ID,
            "qualification_status": "staged_unreviewed",
        }:
            raise ValueError("Benchmark database is missing its isolated staging dataset")
        approved = conn.execute(
            "SELECT count(*) AS n FROM drilling_event WHERE review_state='approved'"
        ).fetchone()["n"]
        if approved:
            raise ValueError("Benchmark staging database contains approved events")
        before = conn.execute(
            """SELECT d.id,d.filename,j.status FROM ingestion_job j
               JOIN source_document d ON d.id=j.document_id
               WHERE d.dataset_id=%s AND j.status IN ('pending','retrying','processing')
               ORDER BY j.created_at LIMIT 1""",
            (DATASET_ID,),
        ).fetchone()
    if not before:
        return {"processed": False, "reason": "no_pending_job"}
    # The worker processes at most one job per tick and keeps drafts unreviewed.
    if not tick():
        return {"processed": False, "reason": "job_not_ready"}
    with connection() as conn:
        after = conn.execute(
            "SELECT ingest_status,page_count FROM source_document WHERE id=%s", (before["id"],)
        ).fetchone()
        approved = conn.execute(
            "SELECT count(*) AS n FROM drilling_event WHERE review_state='approved'"
        ).fetchone()["n"]
        if approved:
            raise ValueError("Unexpected approved event in benchmark staging database")
    return {
        "processed": True,
        "document_id": str(before["id"]),
        "ingest_status": after["ingest_status"],
        "page_count": after["page_count"],
        "approved_events": 0,
    }


def status() -> dict:
    guard()
    with connection() as conn:
        datasets = conn.execute("SELECT id,qualification_status FROM dataset").fetchall()
        if len(datasets) != 1 or datasets[0] != {
            "id": DATASET_ID,
            "qualification_status": "staged_unreviewed",
        }:
            raise ValueError("Benchmark database is missing its isolated staging dataset")
        rows = conn.execute(
            """SELECT d.filename,d.ingest_status,d.page_count,
               count(DISTINCT c.id) AS draft_count
               FROM source_document d LEFT JOIN document_event_draft c ON c.document_id=d.id
               WHERE d.dataset_id=%s GROUP BY d.id ORDER BY d.filename""",
            (DATASET_ID,),
        ).fetchall()
        approved = conn.execute(
            "SELECT count(*) AS n FROM drilling_event WHERE review_state='approved'"
        ).fetchone()["n"]
    if approved:
        raise ValueError("Benchmark staging database contains approved events")
    return {
        "dataset_id": str(DATASET_ID),
        "qualification_status": "staged_unreviewed",
        "documents": rows,
        "approved_events": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage pinned public PDFs without approving events")
    parser.add_argument("action", choices=("prepare", "process-one", "status"))
    parser.add_argument("--raw-dir", type=Path, default=Path("../data/raw/sodir"))
    args = parser.parse_args()
    if args.action == "prepare":
        result = prepare(json.loads(REFERENCE.read_text()), json.loads(QUESTIONS.read_text()), args.raw_dir)
    elif args.action == "process-one":
        result = process_one()
    else:
        result = status()
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
