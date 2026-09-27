"""Offline, transport-neutral feed-change harness; not a WITSML/ETP client."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FeedChange(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    stream_id: str = Field(min_length=1)
    wellbore_id: str = Field(min_length=1)
    channel: str = Field(min_length=1)
    source_record_id: str = Field(min_length=1)
    cursor: int = Field(ge=1)
    revision: int = Field(ge=1)
    operation: Literal["upsert", "delete"]
    observed_at: datetime
    received_at: datetime
    md_m: float = Field(ge=0)
    value: float | None = None
    unit: str | None = None
    quality: Literal["good", "suspect", "bad", "missing"]

    @model_validator(mode="after")
    def check_change(self):
        if self.observed_at.tzinfo is None or self.received_at.tzinfo is None:
            raise ValueError("Source and receipt timestamps must have timezones")
        if self.operation == "upsert" and (self.value is None or not self.unit):
            raise ValueError("Upserts need a finite value and source unit")
        if self.operation == "delete" and (self.value is not None or self.unit is not None):
            raise ValueError("Deletes must not carry a value or unit")
        return self


class Replay(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["feed-contract-replay-v1"]
    source_kind: Literal["synthetic"]
    as_of: datetime
    changes: list[FeedChange]

    @model_validator(mode="after")
    def timezone_required(self):
        if self.as_of.tzinfo is None:
            raise ValueError("as_of must have a timezone")
        return self


class FeedState:
    def __init__(self) -> None:
        self.watermarks: dict[str, int] = {}
        self.cursor_hashes: dict[tuple[str, int], str] = {}
        self.records: dict[tuple[str, str, str], FeedChange] = {}
        self.duplicates = 0
        self.corrections = 0
        self.deletions = 0

    def apply(self, change: FeedChange) -> str:
        cursor_key = (change.stream_id, change.cursor)
        digest = hashlib.sha256(change.model_dump_json().encode()).hexdigest()
        if cursor_key in self.cursor_hashes:
            if self.cursor_hashes[cursor_key] != digest:
                raise ValueError("cursor_collision")
            self.duplicates += 1
            return "duplicate"
        last_cursor = self.watermarks.get(change.stream_id, 0)
        if change.cursor != last_cursor + 1:
            raise ValueError("cursor_gap_or_rewind")
        record_key = (change.stream_id, change.channel, change.source_record_id)
        previous = self.records.get(record_key)
        if previous and change.revision != previous.revision + 1:
            raise ValueError("record_revision_gap_or_rewind")
        if not previous and change.revision != 1:
            raise ValueError("new_record_revision_must_be_one")
        if previous and previous.wellbore_id != change.wellbore_id:
            raise ValueError("record_wellbore_changed")
        if change.operation == "delete" and not previous:
            raise ValueError("cannot_delete_unknown_record")
        self.records[record_key] = change
        self.cursor_hashes[cursor_key] = digest
        self.watermarks[change.stream_id] = change.cursor
        if change.operation == "delete":
            self.deletions += 1
        elif previous:
            self.corrections += 1
        return "applied"

    def latest(self, wellbore_id: str, channel: str, as_of: datetime, stale_seconds=15) -> dict:
        live = [
            record for record in self.records.values()
            if record.wellbore_id == wellbore_id and record.channel == channel
            and record.operation == "upsert" and record.observed_at <= as_of
        ]
        if not live:
            return {"state": "unavailable"}
        current = max(live, key=lambda record: (record.observed_at, record.revision))
        age = (as_of - current.observed_at).total_seconds()
        if current.quality != "good":
            state = "quality_blocked"
        elif age > stale_seconds:
            state = "stale"
        else:
            state = "current"
        return {
            "state": state,
            "source_record_id": current.source_record_id,
            "revision": current.revision,
            "observed_at": current.observed_at.astimezone(timezone.utc).isoformat(),
            "age_seconds": age,
            "quality": current.quality,
        }


def run(replay: Replay) -> dict:
    state = FeedState()
    for change in replay.changes:
        state.apply(change)
    channels = sorted({(c.wellbore_id, c.channel) for c in replay.changes})
    return {
        "schema_version": replay.schema_version,
        "source_kind": replay.source_kind,
        "changes": len(replay.changes),
        "duplicates": state.duplicates,
        "corrections": state.corrections,
        "deletions": state.deletions,
        "watermarks": state.watermarks,
        "channel_states": [state.latest(wellbore, channel, replay.as_of)["state"] for wellbore, channel in channels],
        "live_integration_validated": False,
        "note": "Synthetic contract replay only; no WITSML protocol or OIL connection is exercised.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay synthetic feed changes against local contract")
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    replay = Replay.model_validate_json(args.manifest.read_text())
    print(json.dumps(run(replay), indent=2))


if __name__ == "__main__":
    main()
