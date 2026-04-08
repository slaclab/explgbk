from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from pydantic import AliasChoices, AnyUrl, BaseModel, ConfigDict, Field
from pydantic.types import AwareDatetime

AttachmentID = UUID
LogbookID = UUID
EntryID = UUID
EntryRevisionID = UUID
UserUUID = UUID
TagID = UUID
ShiftID = UUID
RunID = UUID
InstrumentID = UUID
ExperimentID = UUID
ProposalID = UUID
ExternalLinkID = UUID


# =========================================================================
# V2 RELATIONAL DATABASE SCHEMA MAPPING (CROW'S FOOT NOTATION)
# =========================================================================
# Legend:
# || : One and only one
# o< : Zero or more
# |< : One or many
# |o : Zero or one (optional)
#
# --- Core Logbook & Entry Relationships ---
# Entry ||---o< Attachment                   (1:N) An entry can have many attachments.
# Logbook ||---o< LogbookEntry >o---|| Entry (M:N) Entries can be cross-posted to multiple logbooks.
# Tag ||---o< EntryTag >o---|| Entry         (M:N) Entries have multiple tags, tags apply to multiple entries.
# Entry |o---o< Entry                        (1:N) Self-referencing adjacency list for threaded replies (parent to children).
# User ||---o< Entry                         (1:N) A user (primary author) can write many entries.
#
# --- Experiment & Run Relationships ---
# Instrument ||---o< Experiment              (1:N) An instrument hosts many experiments over time.
# Proposal |o---o< Experiment                (1:N) A proposal/grant can fund multiple experiments.
# Experiment ||---|| Logbook                 (1:1) Every experiment is auto-provisioned exactly one primary logbook.
# Experiment ||---o< Run                     (1:N) An experiment consists of many data acquisition runs.
# Run |o---o< Entry                          (1:N) A run can have many log entries associated with it.
#
# --- Instrument Relationships ---
# Instrument ||---|| Logbook                 (1:1) Every instrument gets exactly one primary logbook.
#
# --- Shift Relationships ---
# Instrument ||---o< OperatorShift           (1:N) An instrument hosts many facility operator shifts.
# Experiment ||---o< ExperimentShift         (1:N) An experiment contains many scientific shifts.
# Shift |o---o< Entry                        (1:N) A shift can encompass many log entries.
# User ||---o< OperatorShift                 (1:N) A user can be the assigned operator for many OperatorShifts.
# User ||---o< ExperimentShift               (1:N) A user can be the principal/leader for many ExperimentShifts.
# User ||---o< ShiftMember >o---|| ExperimentShift (M:N) Users participate as members in multiple shifts.
# =========================================================================


class Tag(BaseModel):
    id: TagID = Field(default_factory=uuid4)
    name: str | None
    description: str | None = None


class Attachment(BaseModel):
    id: AttachmentID = Field(default_factory=uuid4)
    legacy_id: str | None = Field(
        default=None,
        description="v1 object id as a hex string, to make sure we dont add duplicates",
    )
    created_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    entry_id: EntryID
    name: str | None = Field(default=None, description="Human readable name")
    description: str | None = Field(
        default=None, description="Optional free-text description"
    )
    filename: str = Field(..., description="Original filename at upload time")
    mime_type: str = Field(
        ..., description="MIME type, e.g. 'image/jpeg'", alias="type"
    )
    size_bytes: int = Field(..., description="Size of the file in bytes")
    uri: AnyUrl = Field(..., description="URI for accessing the attachment data")
    preview_uri: AnyUrl | None = Field(
        default=None, description="URI for accessing a preview (e.g. thumbnail)"
    )


class ExternalLinkBase(BaseModel):
    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)
    id: ExternalLinkID = Field(default_factory=uuid4)
    entry_id: EntryID = Field(
        ..., description="The entry this integration is attached to"
    )


class JiraLink(ExternalLinkBase):
    system: Literal["jira"] = "jira"
    ticket_id: str = Field(..., description="e.g., DATA-1234")
    uri: AnyUrl = Field(..., description="Clickable link to Jira issue")


class SlackLink(ExternalLinkBase):
    system: Literal["slack"] = "slack"
    channel_id: str = Field(..., description="Slack channel ID, e.g. C12345")
    message_ts: str = Field(..., description="Slack message timestamp")
    uri: AnyUrl = Field(..., description="Deep link to the Slack thread")


ExternalLink = Annotated[JiraLink | SlackLink, Field(discriminator="system")]


class Entry(BaseModel):
    id: EntryID = Field(default_factory=uuid4)
    legacy_id: str | None = Field(
        default=None,
        description="v1 object id as a hex string, to make sure we dont add duplicates",
    )
    created_at: AwareDatetime = Field(
        default_factory=lambda: datetime.now(UTC), alias="insert_time"
    )
    ocurred_at: AwareDatetime | None = Field(
        default=None,
        description="Time the event occurred (as opposed to when it was logged)",
        alias="relevance_time",
    )

    # TODO: if data come in without title, we need to ensure that
    # we populate it with a standard placeholder, so that we can erase it
    # on its way back to elogv1
    title: str = Field(..., min_length=1)
    content: str = Field(..., description="Main body of the entry.", alias="text")

    # TODO: need to translate this back to TEXT in elogv1
    content_type: str = Field(default="text/markdown")

    # We want to have one primary, but also allow for additional authors for attribution
    author_id: UserUUID = Field(..., description="Author of the entry")

    # This is how we crosspost
    logbook_ids: set[LogbookID] = Field(
        ..., min_length=1, description="Logbook(s) this entry belongs to"
    )

    version: int = Field(
        default=1, description="Current revision number, incremented on each edit"
    )

    # Retraction of entry by some user at some time
    retracted_by: UserUUID | None = Field(
        default=None, description="Pointer to retraction notice", alias="deleted_by"
    )
    retracted_time: AwareDatetime | None = Field(
        default=None, description="Time of retraction", alias="deleted_time"
    )

    tag_ids: set[TagID] = Field(
        default_factory=set, description="Tags associated with this entry"
    )

    attachment_ids: set[AttachmentID] = Field(
        default_factory=set, description="Attachments associated with this entry"
    )

    # we only use parent + time stamp for threads here
    # on the way back to elogv1, we can just call them the same parent/root
    # TODO: UNLESS we cannot have multiple entries pointing
    # to the same parent+root
    root_id: EntryID | None = Field(default=None, description="For threaded replies")

    # TODO: deal with runs
    run_id: RunID | None = Field(
        default=None, description="Associated run, if any", alias="run_num"
    )

    # TODO: deal with shifts - i think this can be inferred from time of post
    # and shift times, but may be useful to have an explicit pointer for querying
    shift_id: ShiftID | None = Field(
        default=None, description="Associated shift, if any"
    )

    # TODO: we can bring this in later
    external_links: list[ExternalLink] | None = Field(
        default=None, description="List of external URLs to link from the entry"
    )


class EntryRevision(BaseModel):
    id: EntryRevisionID = Field(default_factory=uuid4)
    legacy_id: str | None = Field(
        default=None,
        description="v1 object id as a hex string, to make sure we dont add duplicates",
    )
    entry_id: EntryID = Field(..., description="Entry this revision belongs to")
    version: int = Field(..., description="Version number this revision captures")
    revised_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    revised_by: UserUUID = Field(..., description="User who made the edit")

    # Snapshot of mutable fields at the time this revision was created
    title: str
    content: str = Field(..., alias="text")
    content_type: str
    ocurred_at: AwareDatetime | None = Field(default=None, alias="relevance_time")
    tag_ids: set[TagID] = Field(default_factory=set)
    attachment_ids: set[AttachmentID] = Field(default_factory=set)


class LogbookType(StrEnum):
    EXPERIMENT = "experiment"
    INSTRUMENT = "instrument"


class Logbook(BaseModel):
    id: LogbookID = Field(default_factory=uuid4)
    legacy_id: str | None = Field(
        default=None,
        description="v1 object id as a hex string, to make sure we dont add duplicates",
    )
    created_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))

    type: LogbookType = Field(..., description="Type of logbook")

    name: str = Field(..., min_length=1, description="Unique name of the logbook")
    description: str | None = Field(
        default=None, description="Optional free-text description of the logbook"
    )
    entry_ids: set[EntryID] = Field(
        default_factory=set, description="Entries that belong to this logbook"
    )


class RunType(StrEnum):
    data = "DATA"
    calibration = "CALIBRATION"
    test = "TEST"


class Run(BaseModel):
    id: RunID = Field(default_factory=uuid4)
    num: int = Field(..., description="Run number, e.g. 1234", alias="name")
    name: str | None = Field(..., description="")
    type: RunType = Field(
        ..., description="Type of the run, e.g. 'data', 'calibration', etc."
    )
    start_time: AwareDatetime = Field(
        ..., description="Start time of the run", alias="begin_time"
    )
    end_time: AwareDatetime | None = Field(
        default=None,
        description="End time of the run (if it has ended)",
        alias="end_time",
    )
    meta: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary key-value metadata about the run",
        alias="params",
    )

    # TODO: editable_params and params_modified_time fields from v1
    # TODO: we also have {exp}.run_param_descriptions - this is metadata about the metadata
    # fields, i am thinking we should put this somewhere here


class Experiment(BaseModel):
    id: ExperimentID = Field(default_factory=uuid4)
    meta: dict[str, Any]  # we can store anything about the experiment here

    run_ids: set[RunID] = Field(
        default_factory=set, description="Runs associated with this experiment"
    )
    instrument_id: InstrumentID
    logbook_id: LogbookID

    # TODO: this is in "params" {exp}.info.params in v1
    proposal_id: ProposalID | None = None

    # TODO: not sure if we want this association or not
    shift_ids: set[ShiftID] = Field(
        default_factory=set, description="Shifts associated with this experiment"
    )

    # TODO: roles -
    # I think we should suck up the roles at the experiment level into an openfga
    # instance


class Proposal(BaseModel):
    id: str = Field(..., description="Unique identifier for the proposal")


class InstrumentStatus(StrEnum):
    ONLINE = "online"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


class InstrumentParams(BaseModel):
    # TODO: this is a strange thing on the instrument document
    # probably should just go into "metadata"
    num_stations: int
    elog: str | None = None
    is_standard: bool | None = Field(default=None, alias="isStandard")
    is_mobile: bool | None = Field(default=None, alias="isMobile")
    is_location: bool | None = Field(default=None, alias="isLocation")
    operator_uid: str | None = None


class Instrument(BaseModel):
    id: InstrumentID = Field(default_factory=uuid4)
    name: str = Field(
        ..., min_length=1, description="Unique name of the instrument", alias="_id"
    )
    description: str | None = Field(
        default=None, description="Optional free-text description"
    )
    meta: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary key-value metadata about the instrument",
        alias="params",
    )

    # TODO:
    # roles: list[InstrumentRole] = Field(default_factory=list)
    # color: str | None = None  # TODO: put the color field in "metadata"

    status: InstrumentStatus = InstrumentStatus.ONLINE
    logbook_id: LogbookID
    active_experiment_id: ExperimentID | None = None


# TODO: there is some confusing bits between AD and LCLS logbooks here
# for ex. what is a "LogbookShift"?
class BaseShift(BaseModel):
    id: ShiftID = Field(default_factory=uuid4)
    name: str | None = (
        None  # TODO: point of this? seem like it is always Default in explgbk, unsure about AD
    )
    begin: datetime | None = Field(
        None, validation_alias=AliasChoices("from", "begin_time")
    )
    end: datetime | None = Field(None, validation_alias=AliasChoices("to", "end_time"))
    description: str | None = None

    # TODO: unsure if we need this??? seem to be empty in explgbk
    meta: dict[str, str] = Field(
        default_factory=dict,
        description="Arbitrary key-value metadata about the shift",
        alias="params",
    )


class ExperimentShift(BaseShift):
    principal_id: UserUUID = Field(
        ..., description="Leader for this shift", alias="leader"
    )
    user_ids: set[UserUUID] = Field(
        default_factory=set,
        description="Users that participated in this shift",
        alias="members",
    )


class OperatorShift(BaseShift):
    operator_id: UserUUID
    instrument_id: InstrumentID


# TODO: file catalog:
# we should put file catalog in a different system/service to rapidly process file
# events and avoid coupling it to the logbook data model
# we could publish to a very simple rust-based api endpoint to register data files,
# then we query this api or use some websocket stuff to display in the frontend
# distiller used an "advanced file event watch system..."
# we could poss employ something like this to be reactive
