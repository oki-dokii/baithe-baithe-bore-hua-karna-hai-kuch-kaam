"""Seed the geologically calibrated Assam-Arakan Basin dataset and historical records into NWIS."""

import argparse
import hashlib
import json
from pathlib import Path
from uuid import UUID, uuid5

from psycopg import Connection

from nwis.db import connection

_NAMESPACE = UUID("e7f2b1d3-3b68-45a7-96a9-83c8479a9522")


def stable_id(kind: str, external_id: str) -> UUID:
    return uuid5(_NAMESPACE, f"{kind}:{external_id}")


def seed_assam_basin(conn: Connection, path: Path) -> dict:
    raw = path.read_bytes()
    fixture = json.loads(raw)
    dataset_external = fixture["dataset_id"]
    dataset_id = stable_id("dataset", dataset_external)
    fixture_hash = hashlib.sha256(raw).hexdigest()

    with conn.cursor() as cur:
        cur.execute("SELECT version FROM dataset WHERE id = %s", (dataset_id,))
        existing = cur.fetchone()
        if existing:
            if existing["version"] == fixture_hash:
                return {"dataset_id": dataset_id, "repeated": True}
            cur.execute("DELETE FROM dataset WHERE id = %s", (dataset_id,))

        cur.execute(
            """INSERT INTO dataset(id, external_id, name, kind, version, qualification_status,
               origin_kind, authorization_state, applicability)
               VALUES (%s, %s, %s, 'synthetic', %s, 'demo_fixture', 'synthetic', 'synthetic', 'demo_only')""",
            (dataset_id, dataset_external, fixture["dataset_name"], fixture_hash),
        )

        ref_id = stable_id("depth_reference", dataset_external)
        cur.execute(
            """INSERT INTO depth_reference(id, kind, elevation_above_msl_m, review_state)
               VALUES (%s, %s, %s, 'approved')
               ON CONFLICT (id) DO UPDATE SET elevation_above_msl_m=EXCLUDED.elevation_above_msl_m""",
            (
                ref_id,
                fixture["depth_reference"]["kind"],
                fixture["depth_reference"]["elevation_above_msl_m"],
            ),
        )

        # Ensure all standard Assam formations exist
        formations = {
            "siwalik_dhekiajuli": "Siwalik / Dhekiajuli",
            "girujan": "Girujan Clay",
            "tipam": "Tipam Sandstone",
            "barail": "Barail Arenaceous",
            "kopili": "Kopili Shale",
            "sylhet": "Sylhet Limestone",
        }
        for code, display_name in formations.items():
            cur.execute(
                """INSERT INTO formation(id, basin_name, canonical_code, display_name)
                   VALUES (%s, 'ASSAM_ARAKAN', %s, %s)
                   ON CONFLICT (id) DO NOTHING""",
                (stable_id("formation", code), code, display_name),
            )

        # Insert wells, wellbores, surveys, and formation intervals
        for well in fixture["wells"]:
            well_id = stable_id("well", well["id"])
            bore_id = stable_id("wellbore", well["wellbore_id"])
            lon, lat = well["point"]
            is_active = well["id"] == fixture["active_well_id"]

            cur.execute(
                """INSERT INTO well(id, dataset_id, external_id, name, basin_name, status,
                    surface_point, depth_reference_id)
                   VALUES (%s, %s, %s, %s, 'ASSAM_ARAKAN', %s,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s)
                   ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, status=EXCLUDED.status""",
                (
                    well_id,
                    dataset_id,
                    well["id"],
                    well["name"],
                    "active" if is_active else "historical",
                    lon,
                    lat,
                    ref_id,
                ),
            )

            cur.execute(
                """INSERT INTO wellbore(id, well_id, external_id, status)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status""",
                (bore_id, well_id, well["wellbore_id"], "active" if is_active else "historical"),
            )

            for station in well["survey"]:
                cur.execute(
                    """INSERT INTO trajectory_station(id, wellbore_id, survey_version, md_m, tvd_m)
                       VALUES (%s, %s, 1, %s, %s)
                       ON CONFLICT (id) DO NOTHING""",
                    (
                        stable_id("station", f"{well['wellbore_id']}:{station['md_m']}"),
                        bore_id,
                        station["md_m"],
                        station["tvd_m"],
                    ),
                )

            for fmt in well["formations"]:
                fmt_id = stable_id("formation", fmt["id"])
                interval_id = stable_id("interval", fmt["interval_id"])
                cur.execute(
                    """INSERT INTO formation_interval(id, wellbore_id, formation_id, top_md_m,
                        base_md_m, top_tvd_m, base_tvd_m, depth_reference_id, review_state)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'approved')
                       ON CONFLICT (id) DO NOTHING""",
                    (
                        interval_id,
                        bore_id,
                        fmt_id,
                        fmt["top_m"],
                        fmt["base_m"],
                        fmt["top_m"],
                        fmt["base_m"],
                        ref_id,
                    ),
                )

        # Insert documents and extracted passages
        for doc in fixture["documents"]:
            doc_id = stable_id("document", doc["id"])
            doc_text = "\n".join(page["text"] for page in doc["pages"])
            cur.execute(
                """INSERT INTO source_document(id, dataset_id, external_id, sha256, filename,
                    mime_type, byte_size, page_count, ingest_status)
                   VALUES (%s, %s, %s, %s, %s, 'text/plain', %s, %s, 'fixture_loaded')
                   ON CONFLICT (id) DO NOTHING""",
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
                """INSERT INTO document_wellbore(document_id, wellbore_id)
                   VALUES (%s, %s)
                   ON CONFLICT DO NOTHING""",
                (doc_id, stable_id("wellbore", doc["wellbore_id"])),
            )

            for page in doc["pages"]:
                passage_id = stable_id("passage", f"{doc['id']}:{page['page_number']}")
                cur.execute(
                    """INSERT INTO extracted_passage(id, document_id, page_number, section_label,
                        raw_text, ocr_applied)
                       VALUES (%s, %s, %s, %s, %s, false)
                       ON CONFLICT (id) DO NOTHING""",
                    (
                        passage_id,
                        doc_id,
                        page["page_number"],
                        page["section_label"],
                        page["text"],
                    ),
                )

        # Insert drilling events
        for event in fixture.get("events", []):
            event_id = stable_id("event", f"{event['wellbore_id']}:{event['start_md_m']}")
            bore_id = stable_id("wellbore", event["wellbore_id"])
            passage_id = stable_id("passage", f"{event['document_id']}:{event['page_number']}")
            
            interval_row = cur.execute(
                """SELECT id FROM formation_interval
                   WHERE wellbore_id=%s AND top_md_m <= %s AND base_md_m >= %s LIMIT 1""",
                (bore_id, event["start_md_m"], event["end_md_m"]),
            ).fetchone()
            interval_id = interval_row["id"] if interval_row else None

            source_fields = json.dumps({"quote": event.get("quote", "")})
            cur.execute(
                """INSERT INTO drilling_event(id, external_id, wellbore_id, formation_interval_id,
                    event_type, start_md_m, end_md_m, severity, review_state, description, source_fields)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, 'high', 'approved', %s, %s::jsonb)
                   ON CONFLICT (id) DO UPDATE SET description=EXCLUDED.description, review_state='approved'""",
                (
                    event_id,
                    f"EVT-{event['wellbore_id']}-{int(event['start_md_m'])}",
                    bore_id,
                    interval_id,
                    event["event_type"],
                    event["start_md_m"],
                    event["end_md_m"],
                    event["description"],
                    source_fields,
                ),
            )

            cur.execute(
                """INSERT INTO event_passage(event_id, passage_id)
                   VALUES (%s, %s)
                   ON CONFLICT DO NOTHING""",
                (event_id, passage_id),
            )

            fact_key = f"{event['event_type']}:{event['formation_code']}"
            cur.execute(
                """INSERT INTO reviewed_report_fact(id, dataset_id, fact_key, passage_id, answer,
                    quote, state, reviewer_name)
                   VALUES (%s, %s, %s, %s, %s, %s, 'approved', 'Chief Geologist (Duliajan)')
                   ON CONFLICT (id) DO NOTHING""",
                (
                    stable_id("fact", f"{dataset_external}:{fact_key}:{event['wellbore_id']}"),
                    dataset_id,
                    fact_key,
                    passage_id,
                    event["description"],
                    event.get("quote", event["description"]),
                ),
            )

        cur.execute(
            """INSERT INTO audit_log(actor_name, action, entity_type, entity_id)
               VALUES ('assam-basin-seeder', 'load', 'dataset', %s)""",
            (dataset_id,),
        )

    return {
        "dataset_id": dataset_id,
        "wells": len(fixture["wells"]),
        "events": len(fixture.get("events", [])),
        "documents": len(fixture["documents"]),
        "status": "seeded_successfully",
    }


def main():
    parser = argparse.ArgumentParser(description="Seed Assam-Arakan Basin dataset into NWIS database")
    parser.add_argument(
        "--path",
        type=Path,
        default=Path("specs/fixtures/assam-oil-basin.json"),
        help="Path to Assam basin JSON fixture",
    )
    args = parser.parse_args()
    with connection() as conn:
        result = seed_assam_basin(conn, args.path)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
