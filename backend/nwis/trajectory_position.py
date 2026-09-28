"""Minimum-curvature local coordinates; never an anti-collision calculation."""

import math


def mcm_step(md1: float, i1: float, a1: float, md2: float, i2: float, a2: float):
    """Return north, east and TVD increments in metres for true-north azimuths."""
    values = (md1, i1, a1, md2, i2, a2)
    if not all(math.isfinite(v) for v in values) or md2 <= md1:
        raise ValueError("invalid_survey")
    if not all(0 <= i <= 180 for i in (i1, i2)) or not all(0 <= a < 360 for a in (a1, a2)):
        raise ValueError("invalid_survey")
    i1, a1, i2, a2 = map(math.radians, (i1, a1, i2, a2))
    dmd = md2 - md1
    cosine = math.cos(i1) * math.cos(i2) + math.sin(i1) * math.sin(i2) * math.cos(a2 - a1)
    beta = math.acos(max(-1.0, min(1.0, cosine)))
    if beta >= math.pi - 1e-6:
        raise ValueError("invalid_survey")
    factor = 1.0 if beta < 1e-9 else 2.0 * math.tan(beta / 2.0) / beta
    north = dmd / 2 * (math.sin(i1) * math.cos(a1) + math.sin(i2) * math.cos(a2)) * factor
    east = dmd / 2 * (math.sin(i1) * math.sin(a1) + math.sin(i2) * math.sin(a2)) * factor
    tvd = dmd / 2 * (math.cos(i1) + math.cos(i2)) * factor
    return north, east, tvd


def bottomhole_position(stations, *, azimuth_reference, review_state):
    """Resolve relative bottom-hole N/E only for a reviewed true-north survey."""
    if review_state != "approved":
        raise ValueError("survey_reference_not_reviewed")
    if azimuth_reference != "true":
        raise ValueError("true_north_azimuth_required")
    if len(stations) < 2:
        raise ValueError("survey_missing")
    rows = []
    for station in stations:
        fields = ("md_m", "tvd_m", "inclination_deg", "azimuth_deg")
        if any(station.get(field) is None for field in fields):
            raise ValueError("survey_geometry_incomplete")
        row = tuple(float(station[field]) for field in fields)
        if not all(math.isfinite(v) for v in row):
            raise ValueError("invalid_survey")
        rows.append(row)
    if abs(rows[0][0]) > 1e-6:
        raise ValueError("surface_anchor_missing")
    north = east = 0.0
    for (md1, tvd1, i1, a1), (md2, tvd2, i2, a2) in zip(rows, rows[1:]):
        dn, de, dtvd = mcm_step(md1, i1, a1, md2, i2, a2)
        if abs((tvd2 - tvd1) - dtvd) > max(2.0, (md2 - md1) * 0.01):
            raise ValueError("survey_tvd_inconsistent")
        north += dn
        east += de
    return {"north_m": north, "east_m": east, "terminal_md_m": rows[-1][0],
            "terminal_tvd_m": rows[-1][1], "method": "minimum_curvature_true_north_v1"}
