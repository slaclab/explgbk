"""
Models for run table definitions and run parameter descriptions.

Run tables define configurable tabular views of run data. They can be
per-experiment (in `<exp>.run_tables`) or system-wide templates
(in `site.run_tables`).
"""

from pydantic import Field

from dal.models.common import MongoBaseModel, PyObjectId


class ColumnDefinition(MongoBaseModel):
    """
    A single column in a run table.

    The `source` field is a dotted path into the run document (e.g. "num",
    "params.AMO:HFP:MMS:72.RBV", "editable_params.TAG.value").

    NOTE: The `type` field categorizes the column source (e.g. "run_info",
    "EPICS/...", "Editables") but exact values are not well-enumerated.
    The `mime_type` is added dynamically from run_param_descriptions.
    """

    label: str
    source: str
    type: str | None = None
    mime_type: str | None = None
    description: str | None = None
    category: str | None = None


class RunTable(MongoBaseModel):
    """
    A run table definition document.

    Run tables can be user-defined per experiment, or system-wide templates
    that get cloned into experiments. System tables may be instrument-specific.
    """

    id: PyObjectId | None = Field(None, alias="_id")
    name: str
    coldefs: list[ColumnDefinition] = Field(default_factory=list)
    sort_index: int = 100
    # NOTE: table_type values observed: "generatedtable", "generatedscatter".
    # Not fully enumerated; there may be others.
    table_type: str | None = None
    patterns: str | None = None  # regex for generatedtable
    # Flags (some are computed/added dynamically, not always stored)
    is_system_run_table: bool = False
    is_editable: bool = False
    is_template: bool = False
    instrument: str | None = None  # instrument-specific system table


class RunParamDescription(MongoBaseModel):
    """
    Human-readable description for a run parameter.

    Stored in `<exp>.run_param_descriptions` or `site.run_param_descriptions`.
    """

    id: PyObjectId | None = Field(None, alias="_id")
    param_name: str
    description: str = ""
    type: str | None = None  # MIME type for special display (e.g. "image/png")
    category: str | None = None
