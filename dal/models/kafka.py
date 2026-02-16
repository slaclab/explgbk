"""
Models for Kafka event messages.

All mutating operations in the DAL publish events to Kafka topics.
These events are consumed by the cache layer and potentially external services.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class KafkaEvent(BaseModel):
    """
    The standard Kafka event envelope used throughout the application.

    NOTE: The `value` field contains the business object and its shape
    depends on the topic (e.g. a Run dict for "runs" topic, an ElogEntry
    dict for "elog" topic). We use dict[str, Any] here since the payload
    type varies.
    """

    experiment_name: str
    crud: Literal["Create", "Update", "Delete"] = Field("Create", alias="CRUD")
    value: dict[str, Any] | None = None

    model_config = {"populate_by_name": True}
