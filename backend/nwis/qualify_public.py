"""Register the pinned NOD 511 report identity for a local, review-only source trial."""

import argparse
import hashlib
import re
import subprocess
from pathlib import Path

from nwis.db import connection
from nwis.seed import stable_id

SOURCE_SHA256 = "960aaeed8d8a439f098537ca1c01b2d9e99da19f748fa3f57fbd284424e37de5"
SOURCE_PAGES = 58
DATASET = stable_id("dataset", "NOD-511-source-trial")
WELL = stable_id("well", "NOD-511:25/10-2")
WELLBORE = stable_id("wellbore", "NOD-511:25/10-2 R")
DATUM = stable_id("depth_reference", "NOD-511:RKB")


def verify(path: Path) -> None:
    if hashlib.sha256(path.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("PDF checksum differs from the inspected NOD source")
    info = subprocess.check_output(["pdfinfo", str(path)], text=True)
    match = re.search(r"^Pages:\s+(\d+)\s*$", info, re.MULTILINE)
    if not match or int(match[1]) != SOURCE_PAGES:
        raise ValueError("PDF page count differs from the inspected NOD source")


def register(path: Path) -> None:
    verify(path)
    # Source FactPage gives ED50 geographic coordinates and a 9 m RKB elevation.
    # The report's feet-based event depth lacks an explicit MD/KB statement, so
    # the depth reference stays unapproved and no automatic mapping is allowed.
    lon_ed50 = 2 + 11 / 60 + 35.88 / 3600
    lat_ed50 = 59 + 9 / 60 + 39.27 / 3600
    with connection() as conn:
        conn.execute(
            """INSERT INTO dataset(id,external_id,name,kind,version,license_reference,qualification_status)
            VALUES(%s,'NOD-511-source-trial','NOD wellbore 25/10-2 R','public',%s,%s,'source_trial')
            ON CONFLICT(id) DO NOTHING""",
            (
                DATASET,
                SOURCE_SHA256,
                "NOD open-data page; reported licence document may retain third-party rights",
            ),
        )
        dataset = conn.execute(
            "SELECT version,kind FROM dataset WHERE id=%s", (DATASET,)
        ).fetchone()
        if dataset != {"version": SOURCE_SHA256, "kind": "public"}:
            raise ValueError("Source trial dataset identity was reused with different metadata")
        conn.execute(
            """INSERT INTO depth_reference(id,kind,elevation_above_msl_m,review_state)
            VALUES(%s,'RKB',9,'needs_review') ON CONFLICT(id) DO NOTHING""",
            (DATUM,),
        )
        conn.execute(
            """INSERT INTO well(id,dataset_id,external_id,name,basin_name,field_name,status,
            surface_point,depth_reference_id)
            VALUES(%s,%s,'25/10-2','25/10-2','NORTH SEA',NULL,'historical',
            ST_Transform(ST_SetSRID(ST_MakePoint(%s,%s),4230),4326)::geography,%s)
            ON CONFLICT(id) DO NOTHING""",
            (WELL, DATASET, lon_ed50, lat_ed50, DATUM),
        )
        conn.execute(
            """INSERT INTO wellbore(id,well_id,external_id,status)
            VALUES(%s,%s,'25/10-2 R','historical') ON CONFLICT(id) DO NOTHING""",
            (WELLBORE, WELL),
        )
        row = conn.execute(
            """SELECT b.external_id,w.external_id AS well_external,d.kind,
            ST_X(w.surface_point::geometry) AS lon,ST_Y(w.surface_point::geometry) AS lat,
            r.review_state FROM wellbore b JOIN well w ON w.id=b.well_id
            JOIN dataset d ON d.id=w.dataset_id JOIN depth_reference r ON r.id=w.depth_reference_id
            WHERE b.id=%s AND w.id=%s AND d.id=%s""",
            (WELLBORE, WELL, DATASET),
        ).fetchone()
        if (
            not row
            or row["well_external"] != "25/10-2"
            or row["external_id"] != "25/10-2 R"
            or row["kind"] != "public"
            or row["review_state"] != "needs_review"
        ):
            raise ValueError("Source trial identities conflict with existing records")
    print(f"Registered review-only public source: dataset={DATASET} wellbore={WELLBORE}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Register pinned NOD 511 source identity locally")
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()
    register(args.pdf)


if __name__ == "__main__":
    main()
