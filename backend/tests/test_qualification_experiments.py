import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from nwis.feed_contract import FeedChange, FeedState, Replay, run
from nwis.volve_overlap import Inventory, audit

ROOT = Path(__file__).resolve().parents[2]


def test_volve_example_reports_overlap_without_claiming_training_readiness():
    inventory = Inventory.model_validate_json(
        (ROOT / "specs/fixtures/volve-overlap-example.json").read_text()
    )
    report = audit(inventory)
    assert report["wellbores_in_inventory"] == 2
    assert report["wellbores_with_ddr_and_telemetry"] == 1
    assert report["reviewed_time_depth_joins"] == 0
    assert "time_depth_joins_not_reviewed" in report["blockers"]
    assert not report["training_authorized"]


def test_volve_inventory_requires_unique_bores_and_real_join_inputs():
    example = json.loads((ROOT / "specs/fixtures/volve-overlap-example.json").read_text())
    duplicate = copy.deepcopy(example)
    duplicate["wellbores"].append(duplicate["wellbores"][0])
    with pytest.raises(ValidationError):
        Inventory.model_validate(duplicate)
    unsupported = copy.deepcopy(example)
    unsupported["wellbores"][1]["time_depth_join_reviewed"] = True
    with pytest.raises(ValidationError):
        Inventory.model_validate(unsupported)


def replay():
    return Replay.model_validate_json(
        (ROOT / "specs/fixtures/feed-contract-replay.json").read_text()
    )


def test_feed_replay_is_idempotent_and_late_row_does_not_regress_latest():
    fixture = replay()
    report = run(fixture)
    assert report["duplicates"] == 1
    assert report["corrections"] == 1
    assert report["watermarks"] == {"SYN-FEED-1": 4}
    assert report["channel_states"] == ["current"]
    assert not report["live_integration_validated"]
    state = FeedState()
    for change in fixture.changes:
        state.apply(change)
    latest = state.latest("SYN-A", "flow_in", fixture.as_of)
    assert latest["source_record_id"] == "r2"
    assert state.records[("SYN-FEED-1", "flow_in", "r1")].value == 805


def test_feed_gap_collision_revision_and_delete_checks():
    first = replay().changes[0]
    state = FeedState()
    assert state.apply(first) == "applied"
    assert state.apply(first) == "duplicate"
    with pytest.raises(ValueError, match="cursor_collision"):
        state.apply(first.model_copy(update={"value": 999}))
    with pytest.raises(ValueError, match="cursor_gap"):
        state.apply(first.model_copy(update={"cursor": 3, "source_record_id": "r3"}))
    with pytest.raises(ValueError, match="record_revision"):
        state.apply(first.model_copy(update={"cursor": 2, "revision": 3}))
    with pytest.raises(ValueError, match="cannot_delete_unknown"):
        state.apply(first.model_copy(update={"cursor": 2, "source_record_id": "unknown", "operation": "delete", "value": None, "unit": None}))
    assert state.watermarks == {"SYN-FEED-1": 1}


def test_feed_correction_delete_staleness_and_bad_quality():
    first = replay().changes[0]
    state = FeedState()
    state.apply(first)
    as_of = first.observed_at + timedelta(seconds=16)
    assert state.latest("SYN-A", "flow_in", as_of)["state"] == "stale"
    revised = first.model_copy(update={"cursor": 2, "revision": 2, "quality": "bad"})
    state.apply(revised)
    assert state.latest("SYN-A", "flow_in", as_of)["state"] == "quality_blocked"
    deleted = first.model_copy(update={"cursor": 3, "revision": 3, "operation": "delete", "value": None, "unit": None})
    state.apply(deleted)
    assert state.latest("SYN-A", "flow_in", as_of)["state"] == "unavailable"
    assert state.deletions == 1


def test_feed_rejects_unusable_timestamps_and_values():
    change = replay().changes[0].model_dump()
    change["observed_at"] = datetime(2026, 9, 27, 10, 0)
    with pytest.raises(ValidationError):
        FeedChange.model_validate(change)
    change["observed_at"] = datetime(2026, 9, 27, 10, tzinfo=timezone.utc)
    change["value"] = float("nan")
    with pytest.raises(ValidationError):
        FeedChange.model_validate(change)
