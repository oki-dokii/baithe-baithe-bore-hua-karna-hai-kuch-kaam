from nwis.provenance import may_approve_event, operationally_eligible


def test_source_use_is_fail_closed_and_orthogonal():
    demo = {
        "kind": "synthetic",
        "origin_kind": "synthetic",
        "authorization_state": "synthetic",
        "applicability": "demo_only",
        "qualification_status": "demo_fixture",
    }
    assert may_approve_event(demo)
    assert not operationally_eligible(demo)

    public = {**demo, "kind": "public", "origin_kind": "public_primary",
              "authorization_state": "unverified", "applicability": "review_only",
              "qualification_status": "staged_unreviewed"}
    assert not may_approve_event(public)
    assert not operationally_eligible(public)
    assert not may_approve_event({**public, "qualification_status": "qualified"})
    assert not may_approve_event({**public, "authorization_state": "public_permitted"})
    approved = {**public, "qualification_status": "qualified",
                "authorization_state": "public_permitted", "applicability": "direct_offset"}
    assert may_approve_event(approved)
    assert operationally_eligible(approved)
    assert not may_approve_event({**approved, "origin_kind": "regional_context"})
    assert not may_approve_event({**approved, "origin_kind": "derived"})
