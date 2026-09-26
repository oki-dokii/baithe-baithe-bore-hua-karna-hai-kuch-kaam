from copy import deepcopy

import pytest

from nwis.intelligence import SearchRequest, correlate, interpolate


def context():
    source = dict(
        formation_id="F1",
        dataset_id="synthetic",
        top_md_m=1800,
        base_md_m=2100,
        review_state="approved",
        datum="synthetic_reference",
        datum_review="approved",
        elevation_above_msl_m=0,
    )
    target = source | dict(top_md_m=2000, base_md_m=2300)
    event = dict(review_state="approved", quality_issues=[], start_md_m=1930, end_md_m=1940)
    survey = [dict(md_m=0, tvd_m=0), dict(md_m=2500, tvd_m=2500)]
    return event, source, target, survey, deepcopy(survey)


def test_golden_formation_mapping():
    result = correlate(*context())
    assert result["status"] == "resolved"
    assert result["mapped_start_md_m"] == 2130 and result["mapped_end_md_m"] == 2140
    assert result["method"] == "formation-relative-tvd-offset-v1"


@pytest.mark.parametrize(
    ("position", "field", "value", "reason"),
    [
        (0, "review_state", "draft", "event_not_approved"),
        (0, "quality_issues", ["unknown_depth_unit"], "event_quality_issues"),
        (0, "source_datum", "unknown", "event_datum_mismatch"),
        (0, "source_depth_axis", "TVD", "event_axis_not_md"),
        (0, "start_md_m", 1700, "event_outside_source_interval"),
        (1, "formation_id", "F2", "formation_mismatch"),
        (1, "datum_review", "draft", "depth_reference_missing"),
        (2, "elevation_above_msl_m", None, "depth_reference_missing"),
        (2, "dataset_id", "another", "dataset_mismatch"),
        (2, "base_md_m", 2100, "mapped_interval_outside_target"),
    ],
)
def test_unresolved_context(position, field, value, reason):
    args = list(context())
    args[position][field] = value
    result = correlate(*args)
    assert result["status"] == "unresolved" and result["reason"] == reason
    assert result["mapped_start_md_m"] is None and result["mapped_end_md_m"] is None


def test_no_survey_extrapolation_or_ambiguous_inverse():
    event, source, target, survey, _ = context()
    assert correlate(event, source, target, survey, [])["reason"] == "survey_missing"
    short = [dict(md_m=0, tvd_m=0), dict(md_m=2050, tvd_m=2050)]
    assert (
        correlate(event, source, target, survey, short)["reason"] == "survey_extrapolation_required"
    )
    folded = [dict(md_m=0, tvd_m=0), dict(md_m=2000, tvd_m=2000), dict(md_m=2500, tvd_m=1900)]
    assert correlate(event, source, target, survey, folded)["reason"] == "ambiguous_tvd_inverse"
    assert (
        interpolate([dict(md_m=1000, tvd_m=900), dict(md_m=2000, tvd_m=1500)], 1200, True) == 1500
    )


def test_search_rejects_reversed_and_nonfinite_depths():
    from uuid import uuid4

    for values in ({"min_md_m": 2000, "max_md_m": 1000}, {"min_md_m": float("nan")}):
        with pytest.raises(ValueError):
            SearchRequest(dataset_id=uuid4(), **values)
