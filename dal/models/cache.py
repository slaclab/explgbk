"""
Models for the experiment cache database (explgbk_cache).

The cache stores pre-aggregated experiment summaries for fast listing
and search. It is maintained by Kafka consumers and periodic background
rebuilds.
"""

from datetime import datetime
from typing import Any

from pydantic import Field

from dal.models.common import MongoBaseModel


class CacheRunSummary(MongoBaseModel):
    """
    A minimal run summary stored in the cache's first_run/last_run fields.
    """

    num: int | str
    begin_time: datetime
    end_time: datetime | None = None


class CacheFileTimestamps(MongoBaseModel):
    """
    Aggregated file timestamp info for an experiment.
    """

    first_file_ts: datetime | None = None
    last_file_ts: datetime | None = None
    duration: float | None = None
    hr_duration: list[str] = Field(default_factory=list)


class CachePocFeedback(MongoBaseModel):
    """
    Aggregated POC (point of contact) feedback summary.
    """

    num_items: int = 0
    num_items_4_5: int = 0
    last_modified_by: str | None = None
    last_modified_at: datetime | None = None


class ExperimentCache(MongoBaseModel):
    """
    A cached experiment summary from `explgbk_cache.experiments`.

    This denormalized document combines data from multiple sources
    (experiment info, runs, files, roles, POC feedback) for efficient
    listing and search.
    """

    id: str = Field(alias="_id")
    name: str
    instrument: str
    description: str = ""
    contact_info: str = ""
    start_time: datetime | None = None
    end_time: datetime | None = None
    posix_group: str | None = None
    players: list[str] = Field(default_factory=list)
    post_players: list[str] = Field(default_factory=list)
    run_count: int | None = None
    first_run: CacheRunSummary | None = None
    last_run: CacheRunSummary | None = None
    all_param_names: list[str] = Field(default_factory=list)
    total_data_size: float | None = Field(None, alias="totalDataSize")
    total_files: int | None = Field(None, alias="totalFiles")
    file_timestamps: CacheFileTimestamps | None = None
    poc_feedback: CachePocFeedback | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class DailyBreakdown(MongoBaseModel):
    """
    A single day's aggregated count/size in experiment stats.
    """

    id: datetime = Field(alias="_id")
    run_count: int | None = None
    total_size: float | None = None  # GB


class ExperimentStats(MongoBaseModel):
    """
    Aggregated daily stats from `explgbk_cache.experiment_stats`.
    """

    id: str = Field(alias="_id")
    run_daily_breakdown: list[DailyBreakdown] = Field(
        default_factory=list, alias="runDailyBreakdown"
    )
    data_daily_breakdown: list[DailyBreakdown] = Field(
        default_factory=list, alias="dataDailyBreakdown"
    )
