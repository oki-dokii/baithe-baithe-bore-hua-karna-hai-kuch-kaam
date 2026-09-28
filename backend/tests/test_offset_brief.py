from nwis.offset_brief import build_brief


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
