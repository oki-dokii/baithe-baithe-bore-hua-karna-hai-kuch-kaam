"""Conservative, versioned pre-import screen for historical drilling telemetry.

This detects obviously non-drilling or unusable exports. It does not establish
event labels, future outcome coverage, or engineering approval.
"""

from collections import defaultdict
from statistics import median
from typing import Iterable

from nwis.drilling_parameters import HistoricalSample

SCREEN_VERSION = "drilling-ahead-screen-v2"
MIN_ROWS = 30
MIN_DURATION_MINUTES = 10
MIN_COMPLETE_FRACTION = 0.8
MIN_ACTIVE_ROWS = 10
MIN_DEPTH_ADVANCE_M = 5.0
MIN_ADVANCING_STEPS = 5
MIN_ADVANCING_STEP_M = 0.01
MAX_GAP_MINUTES = 30
CHANNELS = ("rop_m_per_h", "wob_kn", "rpm", "torque_kn_m", "flow_in_l_per_min")


def screen_wellbore(samples: Iterable[HistoricalSample], wellbore_id: str) -> dict:
    current: dict[str, HistoricalSample] = {}
    for row in samples:
        prior = current.get(row.source_record_id)
        if prior is None or row.revision > prior.revision:
            current[row.source_record_id] = row
    rows = sorted(
        (row for row in current.values() if row.operation == "upsert"),
        key=lambda row: (row.observed_at, row.source_record_id),
    )
    blockers: list[str] = []
    if len(rows) < MIN_ROWS:
        blockers.append("too_few_current_rows")
    duration = (rows[-1].observed_at - rows[0].observed_at).total_seconds() / 60 if rows else 0
    if duration < MIN_DURATION_MINUTES:
        blockers.append("insufficient_time_span")
    complete = [row for row in rows if row.quality == "good"
                and all(getattr(row, channel) is not None for channel in CHANNELS)]
    complete_fraction = len(complete) / len(rows) if rows else 0
    if complete_fraction < MIN_COMPLETE_FRACTION:
        blockers.append("insufficient_good_channel_completeness")
    forward = [row for row in complete if row.rig_state == "forward_drilling"]
    active = [row for row in forward if row.rop_m_per_h > 0.5 and row.wob_kn > 2]
    if len(active) < MIN_ACTIVE_ROWS:
        blockers.append("insufficient_on_bottom_drilling_evidence")
    if not forward or max(row.rop_m_per_h for row in forward) - min(
        row.rop_m_per_h for row in forward
    ) < 1:
        blockers.append("rop_constant_or_near_zero_variation")
    if not forward or max(row.wob_kn for row in forward) - min(
        row.wob_kn for row in forward
    ) < 2:
        blockers.append("wob_constant_or_near_zero_variation")
    depth_advance = 0.0
    advancing_steps = 0
    depth_regressions = 0
    if forward:
        depths = [row.md_m for row in forward]
        depth_advance = max(0.0, depths[-1] - depths[0])
        differences = [later - earlier for earlier, later in zip(depths, depths[1:])]
        advancing_steps = sum(diff > MIN_ADVANCING_STEP_M for diff in differences)
        depth_regressions = sum(diff < -1 for diff in differences)
    if depth_advance < MIN_DEPTH_ADVANCE_M or advancing_steps < MIN_ADVANCING_STEPS:
        blockers.append("no_sustained_measured_depth_advance")
    if depth_regressions:
        blockers.append("forward_drilling_depth_regression")
    gaps = [(later.observed_at - earlier.observed_at).total_seconds() / 60
            for earlier, later in zip(rows, rows[1:])]
    largest_gap = max(gaps, default=0)
    if largest_gap > MAX_GAP_MINUTES:
        blockers.append("large_telemetry_gap")
    duplicate_timestamps = sum(gap == 0 for gap in gaps)
    if duplicate_timestamps:
        blockers.append("duplicate_observation_timestamps")
    quality_counts = {quality: sum(row.quality == quality for row in rows)
                      for quality in ("good", "suspect", "bad", "missing")}
    rig_state_counts = {state: sum(row.rig_state == state for row in rows)
                        for state in ("forward_drilling", "circulating", "tripping",
                                      "other", "unknown")}
    return {
        "wellbore_id": wellbore_id,
        "decision": "stop" if blockers else "screen_passed_needs_review",
        "blockers": blockers,
        "current_rows": len(rows),
        "duration_minutes": round(duration, 2),
        "good_complete_rows": len(complete),
        "good_complete_fraction": round(complete_fraction, 4),
        "forward_complete_rows": len(forward),
        "active_drilling_rows": len(active),
        "rop_min_max": [min((r.rop_m_per_h for r in forward), default=None),
                        max((r.rop_m_per_h for r in forward), default=None)],
        "wob_min_max": [min((r.wob_kn for r in forward), default=None),
                        max((r.wob_kn for r in forward), default=None)],
        "measured_depth_advance_m": round(depth_advance, 2),
        "advancing_steps": advancing_steps,
        "depth_regressions": depth_regressions,
        "largest_gap_minutes": round(largest_gap, 2),
        "median_gap_seconds": median(gaps) * 60 if gaps else None,
        "duplicate_timestamps": duplicate_timestamps,
        "quality_counts": quality_counts,
        "rig_state_counts": rig_state_counts,
    }


def screen_batch(samples: Iterable[HistoricalSample]) -> dict:
    grouped = defaultdict(list)
    for row in samples:
        grouped[str(row.wellbore_id)].append(row)
    reports = [screen_wellbore(rows, bore) for bore, rows in sorted(grouped.items())]
    return {
        "screen_version": SCREEN_VERSION,
        "decision": "stop" if not reports or any(r["blockers"] for r in reports)
                    else "screen_passed_needs_review",
        "wellbores": reports,
        "thresholds": {
            "min_current_rows": MIN_ROWS,
            "min_duration_minutes": MIN_DURATION_MINUTES,
            "min_good_complete_fraction": MIN_COMPLETE_FRACTION,
            "min_active_drilling_rows": MIN_ACTIVE_ROWS,
            "min_depth_advance_m": MIN_DEPTH_ADVANCE_M,
            "min_advancing_steps": MIN_ADVANCING_STEPS,
            "min_advancing_step_m": MIN_ADVANCING_STEP_M,
            "max_gap_minutes": MAX_GAP_MINUTES,
        },
        "note": "Screen only; not engineering qualification, event coverage, or ML authorization.",
    }
