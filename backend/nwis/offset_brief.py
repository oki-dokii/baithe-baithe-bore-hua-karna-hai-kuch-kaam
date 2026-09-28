"""Deterministic brief selection from reviewed, cited analogue claims."""

MAX_WELLS = 3
MAX_EVENTS = 6


def build_brief(comparison, get_case):
    offsets = []
    shown = 0
    omitted_uncited = 0
    omitted_unresolved = 0
    event_limit_reached = False
    for candidate in comparison["items"][:MAX_WELLS]:
        events = []
        for mapping in candidate["mappings"]:
            if mapping["status"] != "resolved":
                omitted_unresolved += 1
                continue
            if shown >= MAX_EVENTS:
                event_limit_reached = True
                break
            case = get_case(mapping["event_id"])
            citations = [
                {"document_id": str(e["document_id"]), "filename": e["filename"],
                 "page_number": e["page_number"], "passage_id": str(e["passage_id"])}
                for e in case["evidence"] if e["page_number"] is not None
            ]
            if not citations:
                omitted_uncited += 1
                continue
            events.append({
                "event_id": str(mapping["event_id"]),
                "event_type": mapping["event_type"],
                "description": case["description"][:180],
                "source_start_md_m": mapping["source_start_md_m"],
                "source_end_md_m": mapping["source_end_md_m"],
                "mapped_start_md_m": mapping["mapped_start_md_m"],
                "mapped_end_md_m": mapping["mapped_end_md_m"],
                "citations": citations[:2],
                "citations_truncated": len(citations) > 2,
            })
            shown += 1
        offsets.append({
            "wellbore_id": str(candidate["id"]), "name": candidate["name"],
            "surface_distance_m": candidate["surface_distance_m"],
            "bottomhole_horizontal_distance_m": candidate.get("bottomhole_horizontal_distance_m"),
            "similarity_score": candidate["similarity_score"],
            "data_kind": candidate["data_kind"],
            "origin_kind": candidate["origin_kind"],
            "authorization_state": candidate["authorization_state"],
            "applicability": candidate["applicability"],
            "events": events,
        })
    return {
        "active_name": comparison["active"]["name"],
        "target_formation": comparison["target_interval"]["display_name"],
        "radius_km": comparison["radius_km"],
        "proximity_basis": comparison.get("proximity_basis", "surface"),
        "score_formula": comparison["score_formula"],
        "offsets": offsets,
        "omitted_uncited": omitted_uncited,
        "omitted_unresolved": omitted_unresolved,
        "truncated": comparison["truncated"] or len(comparison["items"]) > MAX_WELLS
                     or event_limit_reached,
        "notice": "Historical, reviewed and cited observations only. Formation-relative mapping and similarity are heuristics, not risk probabilities or operating recommendations. " + (
            "Reviewed true-north terminal positions only; endpoint distance is not collision clearance or a safety assessment."
            if comparison.get("proximity_basis") == "terminal_bottomhole"
            else "Surface radius is not bottom-hole search."
        ),
    }
