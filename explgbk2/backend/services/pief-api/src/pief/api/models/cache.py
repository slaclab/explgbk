from beanie import Document
from pydantic import BaseModel, ConfigDict, Field

from pief.api.models.common import UTCDatetime


class LastRun(BaseModel):
    num: int
    begin_time: UTCDatetime
    end_time: UTCDatetime | None = None


class ExperimentBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    instrument: str | None = None
    contact_info: str | None = None
    leader_account: str | None = None
    posix_group: str | None = None
    params: dict | None = None
    start_time: UTCDatetime | None = None
    end_time: UTCDatetime | None = None
    registration_time: UTCDatetime | None = None
    run_count: int = 0
    players: list[str] = Field(default_factory=list)
    post_players: list[str] = Field(default_factory=list)
    last_run: LastRun | None = None


class Experiment(Document, ExperimentBase):
    """Beanie document backed by explgbk_cache.experiments."""

    # experiment name, maps to MongoDB _id
    id: str  # pyrefly: ignore[bad-override]

    class Settings:
        name = "experiments"


class ExperimentPublic(ExperimentBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: UTCDatetime | None = None


class ExperimentsPublic(BaseModel):
    data: list[ExperimentPublic]
    count: int


class InstrumentSummary(BaseModel):
    instrument: str
    experiment_count: int
