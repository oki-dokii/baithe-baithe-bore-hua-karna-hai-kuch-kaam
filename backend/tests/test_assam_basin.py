"""Unit and contract tests for the Assam-Arakan Basin dataset fixture."""

import json
from pathlib import Path

FIXTURE_PATH = Path("../specs/fixtures/assam-oil-basin.json")
if not FIXTURE_PATH.exists():
    FIXTURE_PATH = Path("specs/fixtures/assam-oil-basin.json")


def test_assam_basin_fixture_structure():
    assert FIXTURE_PATH.exists(), f"Fixture missing at {FIXTURE_PATH}"
    data = json.loads(FIXTURE_PATH.read_text())

    assert data["dataset_id"] == "oil-assam-basin-reference-v1"
    assert data["coordinate_crs"] == "EPSG:4326"
    assert len(data["wells"]) == 5

    well_ids = {w["id"] for w in data["wells"]}
    expected_wells = {"NHK-302", "MOR-045", "DGB-108", "BGJ-015", "KSJ-004"}
    assert well_ids == expected_wells

    # Verify geological intervals & surveys
    for well in data["wells"]:
        assert len(well["point"]) == 2
        lon, lat = well["point"]
        assert 94.0 <= lon <= 96.5  # Upper Assam longitude bounds
        assert 26.5 <= lat <= 28.0  # Upper Assam latitude bounds

        # Formations monotonic
        for fmt in well["formations"]:
            assert fmt["top_m"] < fmt["base_m"]
            assert fmt["id"] in {
                "siwalik_dhekiajuli",
                "girujan",
                "tipam",
                "barail",
                "kopili",
                "sylhet",
            }

        # Survey stations
        for i in range(1, len(well["survey"])):
            assert well["survey"][i]["md_m"] > well["survey"][i - 1]["md_m"]
            assert well["survey"][i]["tvd_m"] >= well["survey"][i - 1]["tvd_m"]

    # Verify documents & events
    assert len(data["documents"]) >= 3
    assert len(data["events"]) >= 5

    for event in data["events"]:
        assert event["event_type"] in ("mud_loss", "stuck_pipe", "kick")
        assert event["start_md_m"] <= event["end_md_m"]
        assert len(event["description"]) > 10
        assert len(event["quote"]) > 5
