import math

import pytest

from nwis.intelligence import position_profile
from nwis.trajectory_position import bottomhole_position, mcm_step


def test_vertical_and_straight_hold():
    assert mcm_step(0, 0, 0, 100, 0, 0) == pytest.approx((0, 0, 100))
    north, east, tvd = mcm_step(0, 30, 60, 100, 30, 60)
    assert north == pytest.approx(100 * math.sin(math.radians(30)) * math.cos(math.radians(60)))
    assert east == pytest.approx(100 * math.sin(math.radians(30)) * math.sin(math.radians(60)))
    assert tvd == pytest.approx(100 * math.cos(math.radians(30)))


def test_reviewed_true_north_survey_resolves_relative_bottomhole():
    rows = [
        {"md_m": 0, "tvd_m": 0, "inclination_deg": 30, "azimuth_deg": 90},
        {"md_m": 100, "tvd_m": 86.60254, "inclination_deg": 30, "azimuth_deg": 90},
    ]
    result = bottomhole_position(rows, azimuth_reference="true", review_state="approved")
    assert result["north_m"] == pytest.approx(0, abs=1e-9)
    assert result["east_m"] == pytest.approx(50)


@pytest.mark.parametrize(
    ("reference", "state", "reason"),
    [
        (None, "approved", "true_north_azimuth_required"),
        ("grid", "approved", "true_north_azimuth_required"),
        ("magnetic", "approved", "true_north_azimuth_required"),
        ("true", "unreviewed", "survey_reference_not_reviewed"),
    ],
)
def test_reference_gate(reference, state, reason):
    with pytest.raises(ValueError, match=reason):
        bottomhole_position([], azimuth_reference=reference, review_state=state)


def test_geometry_fails_closed():
    rows = [
        {"md_m": 0, "tvd_m": 0, "inclination_deg": 0, "azimuth_deg": 0},
        {"md_m": 100, "tvd_m": 100, "inclination_deg": None, "azimuth_deg": None},
    ]
    with pytest.raises(ValueError, match="survey_geometry_incomplete"):
        bottomhole_position(rows, azimuth_reference="true", review_state="approved")
    rows[1].update(inclination_deg=30, azimuth_deg=90)
    with pytest.raises(ValueError, match="survey_tvd_inconsistent"):
        bottomhole_position(rows, azimuth_reference="true", review_state="approved")


def test_new_survey_version_revokes_position_without_new_review():
    identity = {"azimuth_reference": "true", "survey_reference_review_state": "approved",
                "survey_reference_version": 1}
    rows = [
        {"survey_version": 2, "md_m": 0, "tvd_m": 0, "inclination_deg": 0,
         "azimuth_deg": 0},
        {"survey_version": 2, "md_m": 10, "tvd_m": 10, "inclination_deg": 0,
         "azimuth_deg": 0},
    ]
    assert position_profile(identity, rows) == {
        "status": "unresolved", "reason": "survey_version_not_reviewed"
    }
