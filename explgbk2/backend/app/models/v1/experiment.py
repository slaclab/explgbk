from typing import Any

from pydantic import AnyUrl, Field

from app.models.v1.base import MongoInt, MongoModel, PyObjectId, UTCDatetime

# ---------------------------------------------------------------------------
# {exp}.info
# ---------------------------------------------------------------------------


class ExperimentInfo(MongoModel):
    """
    {exp}.info — metadata record for the experiment.
    _id is the experiment name string (e.g. "diadaq13").
    """

    # We will keep all of these inside experiment.metadata
    # in v2

    id: str = Field(alias="_id")  # done
    name: str  # done
    description: str | None = None  # done
    instrument: str | None = None  # done
    contact_info: str | None = None  # done
    leader_account: str | None = None  # done
    posix_group: str | None = None  # done
    data_collection_software: str | None = None  # done
    params: dict[str, Any] | None = None  # done
    start_time: UTCDatetime | None = None  # done
    end_time: UTCDatetime | None = None  # done
    registration_time: UTCDatetime | None = None  # done
    type: str | None = (
        None  # TODO: seem to be either "" or None, so we shouldn't include in v2
    )


# ---------------------------------------------------------------------------
# {exp}.roles
# ---------------------------------------------------------------------------


class ExperimentRole(MongoModel):
    """
    {exp}.roles — role assignments for experiment members.
    Unlike site.roles, these do NOT have a privileges list — only players.
    """

    # TODO: suck up the experiment roles into an openfga instance

    id: PyObjectId = Field(alias="_id")
    app: str
    name: str
    players: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# {exp}.elog
# ---------------------------------------------------------------------------


class ElogAttachment(MongoModel):
    """Attachment subdocument embedded in an ElogEntry."""

    id: PyObjectId = Field(alias="_id")  # done
    name: str  # done
    type: str  # MIME type, e.g. "image/jpeg" # done
    url: AnyUrl  # reference, e.g. "mongo://ObjectIdHex" or HTTP URL # done
    preview_url: str | None = None  # done


class ElogEntry(MongoModel):
    """
    {exp}.elog — an individual logbook entry.

    Optional fields reflect real variation in the collection:
    - shift / run_num / title / tags / attachments are present only on some entries
    - parent / root are set on reply entries
    - deleted_by / deleted_time are set when an entry is soft-deleted
    """

    id: PyObjectId = Field(alias="_id")  # done
    relevance_time: UTCDatetime  # done
    insert_time: UTCDatetime  # done
    author: str  # done
    content: str  # done
    content_type: str = "TEXT"  # done
    shift: PyObjectId | None = (
        None  # TODO: ONLY 1 out of 3,600 entries in my test data have this field
    )
    run_num: int | None = (
        None  # TODO (343 out of 3600 entries have this; should we make it optional in v2?)
    )
    title: str | None = None  # done
    tags: list[str] | None = None  # done
    attachments: list[ElogAttachment] | None = None  # done
    parent: PyObjectId | None = None  # done
    root: PyObjectId | None = None  # done
    deleted_by: str | None = None  # done
    deleted_time: UTCDatetime | None = None  # done
    email_to: list[str] | None = (
        None  # not putting this in v2 - will handle notifications later
    )
    jira_ticket: str | None = (
        None  # external link field - will handle more robustly in v2
    )
    post_to_elogs: list[str] | None = None  # we have as a relationship
    previous_version: PyObjectId | None = None  # we have history tracking


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
    num: int  # TODO
    type: str = ""  # done, but v2 is strenum
    begin_time: UTCDatetime  # done
    end_time: UTCDatetime | None = None  # done
    params: dict[str, Any] = Field(default_factory=dict)  # done
    editable_params: dict[str, Any] = Field(default_factory=dict)  # TODO
    params_modified_time: UTCDatetime | None = None  # TODO


# ---------------------------------------------------------------------------
# {exp}.shifts
# ---------------------------------------------------------------------------


class Shift(MongoModel):
    """
    {exp}.shifts — a shift record.
    members may be absent on older documents.
    """

    id: PyObjectId = Field(alias="_id")
    name: str  # done
    begin_time: UTCDatetime  # done
    end_time: UTCDatetime | None = None  # done
    leader: str | None = None  # done
    members: list[str] = Field(default_factory=list)  # done
    description: str | None = None  # done
    params: dict[str, Any] = Field(default_factory=dict)  # done


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
    run_param_name: str | None = None
    run_param_value: str | None = None


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
