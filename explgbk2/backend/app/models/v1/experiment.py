from typing import Any

from pydantic import Field

from app.models.v1.base import MongoInt, MongoModel, PyObjectId, UTCDatetime

# ---------------------------------------------------------------------------
# {exp}.info
# ---------------------------------------------------------------------------


class ExperimentInfo(MongoModel):
    """
    {exp}.info — metadata record for the experiment.
    _id is the experiment name string (e.g. "diadaq13").
    """

    id: str = Field(alias="_id")
    name: str
    description: str | None = None
    instrument: str | None = None
    contact_info: str | None = None
    leader_account: str | None = None
    posix_group: str | None = None
    data_collection_software: str | None = None
    params: dict[str, Any] | None = None
    start_time: UTCDatetime | None = None
    end_time: UTCDatetime | None = None
    registration_time: UTCDatetime | None = None


# ---------------------------------------------------------------------------
# {exp}.roles
# ---------------------------------------------------------------------------


class ExperimentRole(MongoModel):
    """
    {exp}.roles — role assignments for experiment members.
    Unlike site.roles, these do NOT have a privileges list — only players.
    """

    id: PyObjectId = Field(alias="_id")
    app: str
    name: str
    players: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# {exp}.elog
# ---------------------------------------------------------------------------


class ElogAttachment(MongoModel):
    """Attachment subdocument embedded in an ElogEntry."""

    id: PyObjectId = Field(alias="_id")
    name: str
    type: str  # MIME type, e.g. "image/jpeg"
    url: str  # reference, e.g. "mongo://ObjectIdHex" or HTTP URL
    preview_url: str | None = None


class ElogEntry(MongoModel):
    """
    {exp}.elog — an individual logbook entry.

    Optional fields reflect real variation in the collection:
    - shift / run_num / title / tags / attachments are present only on some entries
    - parent / root are set on reply entries
    - deleted_by / deleted_time are set when an entry is soft-deleted
    """

    id: PyObjectId = Field(alias="_id")
    relevance_time: UTCDatetime
    insert_time: UTCDatetime
    author: str
    content: str
    content_type: str = "TEXT"
    shift: PyObjectId | None = None
    run_num: int | None = None
    title: str | None = None
    tags: list[str] | None = None
    attachments: list[ElogAttachment] | None = None
    parent: PyObjectId | None = None
    root: PyObjectId | None = None
    deleted_by: str | None = None
    deleted_time: UTCDatetime | None = None


# ---------------------------------------------------------------------------
# {exp}.runs
# ---------------------------------------------------------------------------


class Run(MongoModel):
    """
    {exp}.runs — a single DAQ run.

    params / editable_params contain arbitrary EPICS PV names as keys,
    so they are typed as dict[str, Any].
    params_modified_time may be null even when present in the document.
    """

    id: PyObjectId = Field(alias="_id")
    num: int
    type: str = ""
    begin_time: UTCDatetime
    end_time: UTCDatetime | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    editable_params: dict[str, Any] = Field(default_factory=dict)
    params_modified_time: UTCDatetime | None = None


# ---------------------------------------------------------------------------
# {exp}.shifts
# ---------------------------------------------------------------------------


class Shift(MongoModel):
    """
    {exp}.shifts — a shift record.
    members may be absent on older documents.
    """

    id: PyObjectId = Field(alias="_id")
    name: str
    begin_time: UTCDatetime
    end_time: UTCDatetime | None = None
    leader: str | None = None
    members: list[str] = Field(default_factory=list)
    description: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# {exp}.file_catalog
# ---------------------------------------------------------------------------


class FileLocation(MongoModel):
    """Location entry embedded in FileCatalogEntry.locations dict values."""

    asof: UTCDatetime


class FileCatalogEntry(MongoModel):
    """
    {exp}.file_catalog — a file registered with the data catalog.

    Newer entries (gen=2) include absolute_path, gen, and hostname.
    Older entries may have only path, checksum, and timestamps.
    """

    id: PyObjectId = Field(alias="_id")
    path: str
    run_num: int
    checksum: str | None = None
    create_timestamp: UTCDatetime
    modify_timestamp: UTCDatetime
    size: MongoInt | None = None
    locations: dict[str, FileLocation] = Field(default_factory=dict)
    absolute_path: str | None = None
    gen: int | None = None
    hostname: str | None = None


# ---------------------------------------------------------------------------
# {exp}.workflow_definitions
# ---------------------------------------------------------------------------


class WorkflowDefinition(MongoModel):
    """
    {exp}.workflow_definitions — defines an automated workflow.
    trigger values include: "START_OF_RUN", "END_OF_RUN", "MANUAL".
    """

    id: PyObjectId = Field(alias="_id")
    name: str
    executable: str
    trigger: str
    location: str
    parameters: str | None = None
    run_as_user: str | None = None


# ---------------------------------------------------------------------------
# {exp}.workflow_jobs
# ---------------------------------------------------------------------------


class WorkflowJobCounter(MongoModel):
    """Counter subdocument embedded in a WorkflowJob."""

    key: str
    value: str | int


class WorkflowJob(MongoModel):
    """
    {exp}.workflow_jobs — a workflow job instance triggered for a run.

    tool_id, log_file_path, counters are present only after submission/completion.
    """

    id: PyObjectId = Field(alias="_id")
    run_num: int
    def_id: PyObjectId
    user: str
    status: str
    submit_time: UTCDatetime
    tool_id: int | None = None
    log_file_path: str | None = None
    counters: list[WorkflowJobCounter] | None = None


# ---------------------------------------------------------------------------
# {exp}.run_param_descriptions
# ---------------------------------------------------------------------------


class RunParamDescription(MongoModel):
    """
    {exp}.run_param_descriptions — human-readable description for a run parameter.
    _id is an ObjectId; param_name is the EPICS PV / parameter key.
    """

    id: PyObjectId = Field(alias="_id")
    param_name: str
    description: str


# ---------------------------------------------------------------------------
# {exp}.counters
# ---------------------------------------------------------------------------


class Counter(MongoModel):
    """
    {exp}.counters — auto-increment sequences (e.g. next_runnum).
    _id is a string key such as "next_runnum".
    """

    id: str = Field(alias="_id")
    seq: int


# ---------------------------------------------------------------------------
# {exp}.subscribers
# ---------------------------------------------------------------------------


class Subscriber(MongoModel):
    """
    {exp}.subscribers — users subscribed for notifications about this experiment.
    _id is the uid string.
    """

    id: str = Field(alias="_id")
    subscriber: str
    email_address: str
    subscribed_time: UTCDatetime
