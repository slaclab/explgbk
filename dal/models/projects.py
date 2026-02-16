"""
Models for sample preparation projects and grids.

Projects and grids are stored in the `lgbkprjs` database, used
primarily for CryoEM sample preparation tracking.
"""

from typing import Any

from pydantic import Field

from dal.models.common import MongoBaseModel, PyObjectId


class Project(MongoBaseModel):
    """
    A project document from `lgbkprjs.projects`.

    NOTE: Projects can have arbitrary additional metadata fields
    beyond name and players, defined by modal_params validation.
    """

    id: PyObjectId | None = Field(None, alias="_id")
    name: str
    players: list[str] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class Grid(MongoBaseModel):
    """
    A grid document from `lgbkprjs.grids`.

    NOTE: Grids can have arbitrary additional fields defined by
    the sampprepgrid modal_params. Common fields include box,
    boxposition, but any key is possible.
    """

    id: PyObjectId | None = Field(None, alias="_id")
    prjid: PyObjectId
    number: int | str
    box: str | None = None
    boxposition: str | None = None
    exp_name: str | None = None

    model_config = {"extra": "allow"}
