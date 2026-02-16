"""
Common types and base model configuration shared across all models.
"""

from typing import Annotated, Any

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, BeforeValidator


def _validate_object_id(v: Any) -> ObjectId:
    if isinstance(v, ObjectId):
        return v
    if isinstance(v, str) and ObjectId.is_valid(v):
        return ObjectId(v)
    raise ValueError(f"Invalid ObjectId: {v}")


PyObjectId = Annotated[ObjectId, BeforeValidator(_validate_object_id)]
"""A BSON ObjectId that accepts both ObjectId instances and valid hex strings."""


class MongoBaseModel(BaseModel):
    """Base model for all MongoDB document models."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        populate_by_name=True,
    )
