"""
Pydantic v2 models for the MongoDB `site` database.

Collections covered:
  - instruments
  - roles
  - site_config
  - experiment_switch
  - experiment_switch_notifications
  - run_tables
  - instrument_param_descriptions
  - logs
"""

from pydantic import Field

from app.models.v1.base import MongoModel, PyObjectId, UTCDatetime

# ---------------------------------------------------------------------------
# site.instruments
# ---------------------------------------------------------------------------


class InstrumentRole(MongoModel):
    """Embedded role subdocument inside an Instrument."""

    app: str
    name: str
    players: list[str] = Field(default_factory=list)


class Instrument(MongoModel):
    """
    site.instruments — _id is the short instrument name (e.g. "AMO").
    """

    id: str = Field(alias="_id")
    description: str | None = None
    params: dict[str, str] = Field(default_factory=dict)
    roles: list[InstrumentRole] = Field(default_factory=list)
    color: str | None = None


# ---------------------------------------------------------------------------
# site.roles
# ---------------------------------------------------------------------------


class SiteRole(MongoModel):
    """
    site.roles — site-wide role definitions with privilege lists.
    Note: experiment-level roles in {exp}.roles omit the privileges field.
    """

    id: PyObjectId = Field(alias="_id")
    app: str
    name: str
    privileges: list[str] = Field(default_factory=list)
    players: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# site.site_config
# ---------------------------------------------------------------------------


class DmLocation(MongoModel):
    """Data mover location entry embedded in SiteConfig."""

    name: str
    all_experiments: bool
    jid_prefix: str | None = None
    jid_ca_cert: str | None = None
    jid_client_cert: str | None = None
    jid_client_key: str | None = None


class FileTypeConfig(MongoModel):
    """File type definition embedded in SiteConfig.filemanager_file_types."""

    name: str
    label: str
    tooltip: str | None = None
    patterns: list[str] = Field(default_factory=list)
    selected: bool = False


class SiteConfig(MongoModel):
    """site.site_config — singleton document with site-wide configuration."""

    id: PyObjectId = Field(alias="_id")
    dm_mover_prefix: str | None = None
    dm_locations: list[DmLocation] = Field(default_factory=list)
    experiment_spanning_elogs: list[str] = Field(default_factory=list)
    filemanager_file_types: dict[str, FileTypeConfig] | None = None


# ---------------------------------------------------------------------------
# site.experiment_switch
# ---------------------------------------------------------------------------


class ExperimentSwitch(MongoModel):
    """site.experiment_switch — records each experiment switch event."""

    id: PyObjectId = Field(alias="_id")
    experiment_name: str
    instrument: str
    station: int
    switch_time: UTCDatetime
    requestor_uid: str
    is_standby: bool | None = None


# ---------------------------------------------------------------------------
# site.experiment_switch_notifications
# ---------------------------------------------------------------------------


class ExperimentSwitchNotification(MongoModel):
    """site.experiment_switch_notifications — notification sent for a switch."""

    id: PyObjectId = Field(alias="_id")
    switch_oid: PyObjectId
    uid: str
    full_name: str
    email: str
    rank: str
    notified: str


# ---------------------------------------------------------------------------
# site.run_tables  (also appears per-experiment as {exp}.run_tables)
# ---------------------------------------------------------------------------


class RunTableColDef(MongoModel):
    """Column definition embedded in a RunTable."""

    label: str
    type: str
    source: str
    is_editable: bool = False
    position: int


class RunTable(MongoModel):
    """
    site.run_tables / {exp}.run_tables — defines columns for run display tables.
    The `instrument` field is present on site-level run tables only.
    """

    id: PyObjectId = Field(alias="_id")
    name: str
    description: str | None = None
    is_editable: bool = False
    table_type: str | None = None
    sort_index: int | None = None
    coldefs: list[RunTableColDef] = Field(default_factory=list)
    instrument: str | None = None
    patterns: str | None = None
    showvalues: bool | None = None


# ---------------------------------------------------------------------------
# site.instrument_param_descriptions
# ---------------------------------------------------------------------------


class InstrumentParamDescription(MongoModel):
    """site.instrument_param_descriptions — _id is the param name key."""

    id: str = Field(alias="_id")
    description: str


# ---------------------------------------------------------------------------
# site.logs
# ---------------------------------------------------------------------------


class SiteLog(MongoModel):
    """site.logs — audit log for site-level operations."""

    id: PyObjectId = Field(alias="_id")
    collection: str
    uid: str
    group: str
    requestor: str | None = None
    ts: UTCDatetime
    op: str
