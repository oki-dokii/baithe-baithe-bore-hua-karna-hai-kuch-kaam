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


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_id: UUID
    expected_version: int = Field(ge=1)
    decision: Literal["approve", "reject", "correct"]
    rationale: str = Field(min_length=3, max_length=2000)
    fields: Candidate | None = None
    acknowledge_issues: bool = False

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
