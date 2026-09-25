from decimal import Decimal

from nwis.ingestion.contracts import Candidate


def normalize(candidate: Candidate, context: dict) -> tuple[dict, list[str]]:
    issues = []
    unit = (candidate.depth_unit or "").lower().strip()
    factor = (
        Decimal("1")
        if unit in {"m", "meter", "meters", "metre", "metres"}
        else (Decimal("0.3048") if unit in {"ft", "feet", "foot"} else None)
    )
    if factor is None:
        issues.append("unknown_depth_unit")
    if candidate.depth_axis is None:
        issues.append("unknown_depth_axis")
    if not candidate.depth_datum:
        issues.append("unknown_depth_datum")
    elif (
        candidate.depth_datum.casefold().strip() != (context.get("datum") or "").casefold().strip()
    ):
        issues.append("depth_datum_mismatch")
    depths = [candidate.depth_start, candidate.depth_end]
    if any(value is None for value in depths):
        issues.append("incomplete_depth")
    if any(value is not None and value < 0 for value in depths) or (
        all(value is not None for value in depths) and depths[1] < depths[0]
    ):
        issues.append("invalid_depth_interval")
    converted = [
        float(Decimal(str(value)) * factor) if value is not None and factor else None
        for value in depths
    ]
    if "invalid_depth_interval" in issues:
        converted = [None, None]
    intervals = context.get("intervals", [])
    names = {str(candidate.formation_name or "").strip().casefold()}
    matching = [i for i in intervals if names.intersection({n.casefold() for n in i["names"]})]
    if len(matching) != 1:
        issues.append("formation_unresolved")
    if candidate.depth_axis == "TVD":
        issues.append("tvd_to_md_mapping_required")
    if candidate.npt_hours is not None and candidate.npt_hours < 0:
        issues.append("invalid_npt_duration")
    return {
        "event_type": candidate.event_type,
        "start_md_m": converted[0] if candidate.depth_axis == "MD" else None,
        "end_md_m": converted[1] if candidate.depth_axis == "MD" else None,
        "formation_interval_id": matching[0]["id"] if len(matching) == 1 else None,
        "npt_hours": candidate.npt_hours
        if candidate.npt_hours is not None and candidate.npt_hours >= 0
        else None,
    }, issues


def normalization_context(conn, wellbore_id) -> dict:
    row = conn.execute(
        """SELECT r.kind AS datum FROM wellbore b JOIN well w ON w.id=b.well_id
           LEFT JOIN depth_reference r ON r.id=w.depth_reference_id WHERE b.id=%s""",
        (wellbore_id,),
    ).fetchone()
    intervals = conn.execute(
        """SELECT i.id, f.canonical_code, f.display_name, array_remove(array_agg(a.alias),NULL) AS aliases
           FROM formation_interval i JOIN formation f ON f.id=i.formation_id
           JOIN wellbore b ON b.id=i.wellbore_id JOIN well w ON w.id=b.well_id
           LEFT JOIN formation_alias a ON a.formation_id=f.id AND a.dataset_id=w.dataset_id
                AND a.review_state='approved'
           WHERE i.wellbore_id=%s AND i.review_state='approved'
           GROUP BY i.id, f.canonical_code, f.display_name""",
        (wellbore_id,),
    ).fetchall()
    return {
        "datum": row["datum"] if row else None,
        "intervals": [
            {"id": str(i["id"]), "names": [i["canonical_code"], i["display_name"], *i["aliases"]]}
            for i in intervals
        ],
    }
