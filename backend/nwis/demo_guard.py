"""Refuse to label a mixed or multiplied database as the one-source demo."""

import argparse

from nwis.config import get_settings
from nwis.db import connection
from nwis.seed import stable_id
from nwis.semantic import model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-unindexed", action="store_true")
    args = parser.parse_args()
    if get_settings().environment == "production":
        raise SystemExit("Demo guard refuses a production environment")
    dataset_id = stable_id("dataset", "nwis-synthetic-golden-v1")
    with connection() as conn:
        rows = conn.execute(
            """SELECT count(*) AS n, count(*) FILTER (WHERE s.event_id IS NOT NULL) AS indexed
               FROM drilling_event e JOIN wellbore b ON b.id=e.wellbore_id
               JOIN well w ON w.id=b.well_id
               LEFT JOIN event_embedding s ON s.event_id=e.id
               WHERE w.dataset_id=%s AND e.review_state='approved'
                 AND EXISTS(SELECT 1 FROM event_passage ep WHERE ep.event_id=e.id)""",
            (dataset_id,),
        ).fetchone()
        datasets = conn.execute("SELECT count(*) AS n FROM dataset").fetchone()["n"]
        fixture = conn.execute("SELECT kind FROM dataset WHERE id=%s", (dataset_id,)).fetchone()
    if (
        datasets != 1
        or not fixture
        or fixture["kind"] != "synthetic"
        or rows["n"] != 1
        or (not args.allow_unindexed and rows["indexed"] != 1)
    ):
        raise SystemExit("Demo DB is not the isolated one-source synthetic scenario")
    if get_settings().semantic_enabled:
        # Fix #10: Only attempt to load the semantic model when the feature
        # is explicitly enabled.  Previously this call was unconditional and
        # would crash the guard script whenever the optional `fastembed`
        # package was absent (i.e. `semantic` extra not installed).
        model()  # Fail fast if semantic is on but weights are missing.
        print("Semantic model loaded successfully")
    print("One-source synthetic demo guard passed")


if __name__ == "__main__":
    main()
