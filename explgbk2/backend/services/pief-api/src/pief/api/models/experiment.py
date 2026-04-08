from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ExperimentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    start_time: datetime
    end_time: datetime | None
    instrument_id: UUID | None
    legacy_id: str | None
    created_at: datetime | None
    updated_at: datetime | None


class ExperimentsPublic(BaseModel):
    data: list[ExperimentPublic]
    count: int


class InstrumentSummary(BaseModel):
    instrument_id: UUID | None
    experiment_count: int
