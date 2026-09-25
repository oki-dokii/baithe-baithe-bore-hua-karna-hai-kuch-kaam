from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ComponentStatus(BaseModel):
    state: str
    detail: str | None = None


class SystemStatus(BaseModel):
    environment: str
    source_mode: str
    database: ComponentStatus
    spatial: ComponentStatus
    vector: ComponentStatus
    ingestion: ComponentStatus
    replay: ComponentStatus
    prediction: ComponentStatus
    datasets: list[str]
    checked_at: datetime


class WellSummary(BaseModel):
    id: UUID
    external_id: str
    name: str
    basin_name: str | None
    data_kind: str
    longitude: float
    latitude: float
    surface_distance_m: float | None = None


class WellPage(BaseModel):
    items: list[WellSummary]
    next_cursor: str | None = None


class NearbyQuery(BaseModel):
    active_well_id: UUID
    radius_km: float = Field(ge=0.1, le=100)


class SeedResponse(BaseModel):
    dataset_id: UUID
    wells: int
    events: int
    documents: int
    repeated: bool


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorBody
    request_id: str
