from nwis.offset_brief import MAX_EVENTS, MAX_WELLS, build_brief


def test_brief_keeps_only_resolved_cited_approved_case_data():
    comparison = {
        "active": {"name": "SYN-A"},
        "target_interval": {"display_name": "F1"},
        "radius_km": 5,
        "score_formula": "heuristic",
        "truncated": False,
        "items": [{
            "id": "b", "name": "SYN-B", "surface_distance_m": 300,
            "similarity_score": 0.9, "data_kind": "synthetic", "origin_kind": "synthetic",
            "authorization_state": "synthetic", "applicability": "demo_only",
            "mappings": [
                {"event_id": "unresolved", "status": "unresolved"},
                {"event_id": "uncited", "status": "resolved"},
                {"event_id": "cited", "status": "resolved", "event_type": "mud_loss",
                 "source_start_md_m": 100, "source_end_md_m": 110,
                 "mapped_start_md_m": 120, "mapped_end_md_m": 130},
            ],
        }],
    }
    cases = {
        "uncited": {"description": "No source", "evidence": []},
        "cited": {"description": "Reviewed incident", "evidence": [
            {"document_id": "d", "filename": "report.pdf", "page_number": 3,
             "passage_id": "p"},
        ]},
    }
    result = build_brief(comparison, cases.__getitem__)
    assert len(result["offsets"][0]["events"]) == 1
    assert result["offsets"][0]["events"][0]["citations"][0]["page_number"] == 3
    assert result["omitted_uncited"] == 1
    assert result["omitted_unresolved"] == 1
    assert "not risk probabilities" in result["notice"]


def test_brief_caps_events_and_wells_with_explicit_truncation():
    def candidate(index, count):
        return {
            "id": f"b{index}", "name": f"SYN-{index}", "surface_distance_m": index + 1,
            "similarity_score": 1, "data_kind": "synthetic", "origin_kind": "synthetic",
            "authorization_state": "synthetic", "applicability": "demo_only",
            "mappings": [{
                "event_id": f"e{index}-{i}", "status": "resolved", "event_type": "mud_loss",
                "source_start_md_m": 100, "source_end_md_m": 100,
                "mapped_start_md_m": 100, "mapped_end_md_m": 100,
            } for i in range(count)],
        }

    comparison = {
        "active": {"name": "SYN-A"}, "target_interval": {"display_name": "F1"},
        "radius_km": 5, "score_formula": "heuristic", "truncated": False,
        "items": [candidate(0, MAX_EVENTS + 1)]
                 + [candidate(i, 0) for i in range(1, MAX_WELLS + 1)],
    }
    def get_case(event_id):
        return {"description": event_id, "evidence": [{
            "document_id": "d", "filename": "synthetic.txt", "page_number": 1,
            "passage_id": "p",
        }]}

    result = build_brief(comparison, get_case)
    assert len(result["offsets"]) == MAX_WELLS
    assert sum(len(well["events"]) for well in result["offsets"]) == MAX_EVENTS
    assert result["truncated"] is True

    comparison["items"] = [candidate(0, MAX_EVENTS)]
    assert build_brief(comparison, get_case)["truncated"] is False


def test_brief_counts_uncited_and_unresolved_without_disclosing_them():
    mappings = [
        {"event_id": "no-depth", "status": "unresolved"},
        {"event_id": "no-source", "status": "resolved"},
    ]
    comparison = {
        "active": {"name": "SYN-A"}, "target_interval": {"display_name": "F1"},
        "radius_km": 5, "score_formula": "heuristic", "truncated": False,
        "items": [{"id": "b", "name": "SYN-B", "surface_distance_m": 1,
                   "similarity_score": 1, "data_kind": "synthetic",
                   "origin_kind": "synthetic", "authorization_state": "synthetic",
                   "applicability": "demo_only", "mappings": mappings}],
    }
    result = build_brief(comparison, lambda _: {"description": "x", "evidence": []})
    assert result["omitted_uncited"] == 1
    assert result["omitted_unresolved"] == 1
    assert result["offsets"][0]["events"] == []
