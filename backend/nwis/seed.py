"""Load the owned, fictional golden fixture into an empty or previously seeded database."""

import argparse
import hashlib
import json
from pathlib import Path
from uuid import UUID, uuid5

from psycopg import Connection

from nwis.db import connection

_NAMESPACE = UUID("6cc56f36-a442-4eb2-8adb-e827ab0bb99e")


def stable_id(kind: str, external_id: str) -> UUID:
    return uuid5(_NAMESPACE, f"{kind}:{external_id}")


def load_fixture(conn: Connection, path: Path) -> dict:
    raw = path.read_bytes()
    fixture = json.loads(raw)
    if fixture.get("data_kind") != "synthetic":
        raise ValueError("Only owned synthetic fixtures may be loaded by this command")
    dataset_external = fixture["dataset_id"]
    dataset_id = stable_id("dataset", dataset_external)
    fixture_hash = hashlib.sha256(raw).hexdigest()
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM dataset WHERE id = %s", (dataset_id,))
        existing = cur.fetchone()
        if existing:
            if existing["version"] != fixture_hash:
                raise ValueError("Fixture ID already exists with different contents")
            return {"dataset_id": dataset_id, "wells": 0, "events": 0, "documents": 0, "repeated": True}

        cur.execute(
            """INSERT INTO dataset(id, external_id, name, kind, version, qualification_status)
               VALUES (%s,%s,%s,'synthetic',%s,'demo_fixture')""",
            (dataset_id, dataset_external, "Golden fictional demo", fixture_hash),
        )
        ref_id = stable_id("depth_reference", dataset_external)
        cur.execute(
            """INSERT INTO depth_reference(id, kind, elevation_above_msl_m, review_state)
               VALUES (%s,%s,%s,'approved')""",
            (
                ref_id,
                fixture["depth_reference"]["kind"],
                fixture["depth_reference"]["elevation_above_msl_m"],
            ),
        )
        formation_codes = {w["formation"]["id"] for w in fixture["wells"]}
        for code in formation_codes:
            cur.execute(
                """INSERT INTO formation(id, basin_name, canonical_code, display_name)
                   VALUES (%s,'SYNTHETIC',%s,%s)""",
                (stable_id("formation", code), code, code),
            )

        for well in fixture["wells"]:
            well_id = stable_id("well", well["id"])
            bore_id = stable_id("wellbore", well["wellbore_id"])
            lon, lat = well["point"]
            cur.execute(
                """INSERT INTO well(id, dataset_id, external_id, name, basin_name, status,
                    surface_point, depth_reference_id)
                   VALUES (%s,%s,%s,%s,'SYNTHETIC',%s,
                    ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography,%s)""",
                (
                    well_id,
                    dataset_id,
                    well["id"],
                    well["id"],
                    "active" if well["id"] == fixture["active_well_id"] else "historical",
                    lon,
                    lat,
                    ref_id,
                ),
            )
            cur.execute(
                "INSERT INTO wellbore(id, well_id, external_id, status) VALUES (%s,%s,%s,%s)",
                (bore_id, well_id, well["wellbore_id"], "active" if well["id"] == fixture["active_well_id"] else "historical"),
            )
            for station in well["survey"]:
                cur.execute(
                    """INSERT INTO trajectory_station(id, wellbore_id, survey_version, md_m, tvd_m)
                       VALUES (%s,%s,1,%s,%s)""",
                    (
                        stable_id("station", f"{well['wellbore_id']}:{station['md_m']}"),
                        bore_id,
                        station["md_m"],
                        station["tvd_m"],
                    ),
                )
            interval = well["formation"]
            cur.execute(
                """INSERT INTO formation_interval(id, wellbore_id, formation_id, top_md_m,
                    base_md_m, top_tvd_m, base_tvd_m, depth_reference_id, review_state)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'approved')""",
                (
                    stable_id("interval", interval["interval_id"]),
                    bore_id,
                    stable_id("formation", interval["id"]),
                    interval["top_m"],
                    interval["base_m"],
                    interval["top_m"],
                    interval["base_m"],
                    ref_id,
                ),
            )

        for doc in fixture["documents"]:
            doc_id = stable_id("document", doc["id"])
            doc_text = "\n".join(page["text"] for page in doc["pages"])
            cur.execute(
                """INSERT INTO source_document(id, dataset_id, external_id, sha256, filename,
                    mime_type, byte_size, page_count, ingest_status)
                   VALUES (%s,%s,%s,%s,%s,'text/plain',%s,%s,'fixture_loaded')""",
                (
                    doc_id,
                    dataset_id,
                    doc["id"],
                    hashlib.sha256(doc_text.encode()).hexdigest(),
                    f"{doc['id']}.txt",
                    len(doc_text.encode()),
                    len(doc["pages"]),
                ),
            )
            cur.execute(
                "INSERT INTO document_wellbore(document_id, wellbore_id) VALUES (%s,%s)",
                (doc_id, stable_id("wellbore", doc["wellbore_id"])),
            )
            for page in doc["pages"]:
                cur.execute(
                    """INSERT INTO extracted_passage(id, document_id, page_number, section_label,
                        raw_text, ocr_applied)
                       VALUES (%s,%s,%s,%s,%s,false)""",
                    (
                        stable_id("passage", f"{doc['id']}:{page['page_number']}"),
                        doc_id,
                        page["page_number"],
                        page["section"],
                        page["text"],
                    ),
                )

        for event in fixture["events"]:
            event_id = stable_id("event", event["id"])
            cur.execute(
                """INSERT INTO drilling_event(id, external_id, wellbore_id,
                    formation_interval_id, event_type, start_md_m, end_md_m, severity,
                    review_state, description)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    event_id,
                    event["id"],
                    stable_id("wellbore", event["wellbore_id"]),
                    stable_id("interval", event["formation_interval_id"]),
                    event["event_type"],
                    event["start_md_m"],
                    event["end_md_m"],
                    event["severity"],
                    event["initial_review_state"],
                    "Fictional mud-loss event from the synthetic report",
                ),
            )
            cur.execute(
                "INSERT INTO event_passage(event_id, passage_id) VALUES (%s,%s)",
                (event_id, stable_id("passage", f"{event['document_id']}:{event['page_number']}")),
            )
            if event.get("recorded_action"):
                cur.execute(
                    "INSERT INTO mitigation(id, event_id, action_taken) VALUES (%s,%s,%s)",
                    (stable_id("mitigation", event["id"]), event_id, event["recorded_action"]),
                )
            cur.execute(
                "INSERT INTO event_outcome(id, event_id, outcome) VALUES (%s,%s,%s)",
                (stable_id("outcome", event["id"]), event_id, event["outcome"]),
            )
            cur.execute(
                """INSERT INTO npt_event(id, event_id, duration_h, duration_source)
                   VALUES (%s,%s,%s,'synthetic_fixture')""",
                (stable_id("npt", event["id"]), event_id, event["npt_duration_h"]),
            )
        cur.execute(
            "INSERT INTO audit_log(actor_name, action, entity_type, entity_id) VALUES ('fixture-loader','load','dataset',%s)",
            (dataset_id,),
        )
    return {
        "dataset_id": dataset_id,
        "wells": len(fixture["wells"]),
        "events": len(fixture["events"]),
        "documents": len(fixture["documents"]),
        "repeated": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    with connection() as conn:
        result = load_fixture(conn, args.path)
    print(json.dumps(result, default=str))


if __name__ == "__main__":
    main()
