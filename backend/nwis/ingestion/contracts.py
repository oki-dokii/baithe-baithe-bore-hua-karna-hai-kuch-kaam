from datetime import datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Hazard = Literal[
    "mud_loss",
    "kick",
    "stuck_pipe",
    "overpressure",
    "torque_spike",
    "tight_hole",
    "fishing",
    "cementing_issue",
    "other",
]


class Candidate(BaseModel):
    """Every provider field is required; absent facts must be explicit nulls."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    event_type: Hazard
    quote: str = Field(min_length=1, max_length=12000)
    description: str = Field(min_length=1, max_length=2000)
    depth_start: float | None
    depth_end: float | None
    depth_unit: str | None
    depth_axis: Literal["MD", "TVD"] | None
    depth_datum: str | None
    formation_name: str | None
    severity: Literal["low", "medium", "high", "critical"] | None
    mitigation: str | None
    outcome: Literal["successful", "partial", "unsuccessful", "unknown"] | None
    npt_hours: float | None


class CandidateBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    events: list[Candidate] = Field(max_length=100)


class OnsetReview(BaseModel):
    """Reviewer-supplied source-time bounds, never inferred from upload time."""

    model_config = ConfigDict(extra="forbid")
    basis: Literal["exact_timelog", "day_only_ddr", "shift_report", "unspecified"]
    earliest: datetime | None = None
    latest: datetime | None = None

    @model_validator(mode="after")
    def valid_bounds(self):
        if self.basis == "unspecified":
            if self.earliest is not None or self.latest is not None:
                raise ValueError("Unspecified onset cannot have time bounds")
            return self
        if self.earliest is None or self.latest is None:
            raise ValueError("Timed onset requires both bounds")
        if self.earliest.tzinfo is None or self.latest.tzinfo is None:
            raise ValueError("Onset bounds must include a timezone")
        if self.earliest > self.latest:
            raise ValueError("Earliest onset must not follow latest")
        if self.basis == "exact_timelog" and self.earliest != self.latest:
            raise ValueError("Exact timelog onset must have equal bounds")
        if self.basis == "day_only_ddr" and not (
            self.earliest.date() == self.latest.date()
            and self.earliest.time() == time.min
            and self.latest.time() == time.max
        ):
            raise ValueError("Day-only DDR bounds must cover the full local reporting day")
        return self


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_id: UUID
    expected_version: int = Field(ge=1)
    decision: Literal["approve", "reject", "correct"]
    rationale: str = Field(min_length=3, max_length=2000)
    fields: Candidate | None = None
    acknowledge_issues: bool = False
    onset: OnsetReview = Field(default_factory=lambda: OnsetReview(basis="unspecified"))

    @model_validator(mode="after")
    def correction_requires_fields(self):
        if self.decision == "correct" and self.fields is None:
            raise ValueError("A correction must include the revised fields")
        return self


class ManualCandidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_number: int = Field(ge=1)
    expected_version: int = Field(ge=1)
    fields: Candidate
    rationale: str = Field(min_length=3, max_length=2000)


class IngestionFailure(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False):
        self.code, self.message, self.retryable = code, message, retryable
        super().__init__(message)
