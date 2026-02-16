"""
Models for sample documents.

Samples are stored in the `samples` collection of each experiment database.
The current sample is tracked in the `current` collection.
"""

from pydantic import Field

from dal.models.common import MongoBaseModel, PyObjectId


class Sample(MongoBaseModel):
    """
    A sample document from the `samples` collection.

    NOTE: Samples can have arbitrary additional fields beyond name and
    description, defined by modal_params validation (loaded from JSON
    config files). The `extra="allow"` setting accommodates this.

    The `current` field is computed on read (not stored in DB) to indicate
    whether this is the currently active sample.
    """

    id: PyObjectId | None = Field(None, alias="_id")
    name: str
    description: str = ""
    # Computed on read
    current: bool | None = None

    model_config = {"extra": "allow"}


class CurrentSample(MongoBaseModel):
    """
    Document in the `current` collection that tracks which sample is active.

    There is exactly one document with _id="sample".
    """

    id: str = Field("sample", alias="_id")
    sample: PyObjectId
