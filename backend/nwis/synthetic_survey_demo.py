"""Attest only the owned, vertical golden fixture's survey geometry for demo use."""

import json

from nwis.config import get_settings
from nwis.db import connection
from nwis.seed import stable_id

DATASET = stable_id("dataset", "nwis-synthetic-golden-v1")
BORES = (stable_id("wellbore", "SYN-A-MAIN"), stable_id("wellbore", "SYN-B-MAIN"))
REVIEWER = "owned-synthetic-fixture-attestation"
REFERENCE = "specs/fixtures/golden-demo.json: all_wells_vertical, md_equals_tvd"


def attest(conn) -> dict:
    dataset = conn.execute(
        """SELECT kind,origin_kind,authorization_state,applicability
           FROM dataset WHERE id=%s""", (DATASET,),
    ).fetchone()
    if dataset != {"kind": "synthetic", "origin_kind": "synthetic",
                   "authorization_state": "synthetic", "applicability": "demo_only"}:
        raise ValueError("Only the owned synthetic golden dataset may be attested")
    changed = []
    for bore_id in BORES:
        bore = conn.execute(
            """SELECT b.*,w.dataset_id FROM wellbore b JOIN well w ON w.id=b.well_id
               WHERE b.id=%s FOR UPDATE OF b""", (bore_id,),
        ).fetchone()
        if not bore or bore["dataset_id"] != DATASET:
            raise ValueError("Synthetic fixture wellbore missing or wrong dataset")
        stations = conn.execute(
            """SELECT survey_version,md_m,tvd_m,inclination_deg,azimuth_deg
               FROM trajectory_station WHERE wellbore_id=%s ORDER BY survey_version,md_m""",
            (bore_id,),
        ).fetchall()
        if len(stations) != 2 or any(
            int(s["survey_version"]) != 1
            or (float(s["md_m"]), float(s["tvd_m"])) not in ((0, 0), (2500, 2500))
            or (s["inclination_deg"] is not None and float(s["inclination_deg"]) != 0)
            or (s["azimuth_deg"] is not None and float(s["azimuth_deg"]) != 0)
            for s in stations
        ) or {float(s["md_m"]) for s in stations} != {0, 2500}:
            raise ValueError("Synthetic survey no longer matches the vertical fixture")
        if bore["survey_reference_review_state"] == "approved":
            if (bore["azimuth_reference"] != "true"
                or bore["survey_reference_version"] != 1
                or bore["survey_reference_reviewed_by"] != REVIEWER
                or bore["survey_reference_review_reference"] != REFERENCE):
                raise ValueError("Existing survey approval has different provenance")
            continue
        if any(bore[field] is not None for field in (
            "azimuth_reference", "survey_reference_version", "survey_reference_reviewed_by",
            "survey_reference_review_reference",
        )):
            raise ValueError("Existing unreviewed survey metadata needs manual inspection")
        conn.execute(
            """UPDATE trajectory_station SET inclination_deg=0,azimuth_deg=0
               WHERE wellbore_id=%s AND survey_version=1""", (bore_id,),
        )
        conn.execute(
            """UPDATE wellbore SET azimuth_reference='true',
               survey_reference_review_state='approved',survey_reference_version=1,
               survey_reference_reviewed_by=%s,survey_reference_review_reference=%s
               WHERE id=%s""", (REVIEWER, REFERENCE, bore_id),
        )
        conn.execute(
            """INSERT INTO audit_log(actor_name,action,entity_type,entity_id,details)
               VALUES (%s,'synthetic_survey_attestation','wellbore',%s,%s::jsonb)""",
            (REVIEWER, bore_id, json.dumps({"reference": REFERENCE, "survey_version": 1,
                                            "synthetic_only": True})),
        )
        changed.append(str(bore_id))
    return {"synthetic_only": True, "attested_wellbores": changed}


def main() -> None:
    if get_settings().environment == "production":
        raise SystemExit("Synthetic survey attestation refuses production")
    with connection() as conn:
        result = attest(conn)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
