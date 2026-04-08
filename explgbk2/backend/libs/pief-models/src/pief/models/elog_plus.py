from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, Field
from pydantic.alias_generators import to_camel

# --- Base Model Configuration ---


class BaseModel(PydanticBaseModel):
    """
    Custom base model that automatically maps snake_case attributes to camelCase JSON.
    Using validate_by_name=True and validate_by_alias=True replaces the
    deprecated populate_by_name=True behavior in Pydantic v2.11+.
    """

    model_config = ConfigDict(
        alias_generator=to_camel, validate_by_name=True, validate_by_alias=True
    )


# --- Enums ---


class PermissionType(StrEnum):
    Read = "Read"
    Write = "Write"
    Admin = "Admin"


class ResourceType(StrEnum):
    All = "All"
    Group = "Group"
    Logbook = "Logbook"


class OwnerType(StrEnum):
    User = "User"
    Group = "Group"
    Token = "Token"


# --- Common / Nested Models ---


class LogbookSummary(BaseModel):
    id: str | None = None
    name: str | None = None
    retired: bool | None = None
    apply_tag_color_to_entry: bool | None = None


class Tag(BaseModel):
    id: str | None = None  # done
    name: str | None = None  # done
    description: str | None = None  # done
    color: str | None = None  # done
    logbook: LogbookSummary | None = None  # TODO: not sure of the relation here


class Shift(BaseModel):
    id: str | None = None  # done
    name: str | None = None  # done
    # Explicit aliases remain since "from" is not the camelCase of "from_time"
    from_time: datetime | None = Field(None, alias="from")  # done
    to_time: datetime | None = Field(None, alias="to")  # done


class LogbookShift(BaseModel):  # TODO: what does this mean?
    id: str | None = None
    logbook: LogbookSummary | None = None
    name: str | None = None
    from_time: datetime | None = Field(None, alias="from")
    to_time: datetime | None = Field(None, alias="to")


class Person(BaseModel):
    uid: str | None = None
    common_name: str | None = None
    surname: str | None = None
    gecos: str | None = None
    mail: str | None = None


class Summarizes(BaseModel):
    shift_id: str | None = None
    date: date | None = None


class DetailsAuthorization(BaseModel):
    id: str | None = None
    owner_id: str | None = None
    owner_name: str | None = None
    owner_type: OwnerType | None = None
    resource_id: str | None = None
    resource_type: ResourceType | None = None
    resource_name: str | None = None
    permission: PermissionType | None = None


# --- Request Models ---


class UpdateLogbook(BaseModel):
    name: str | None = None
    read_all: bool | None = None
    write_all: bool | None = None
    retired: bool | None = None
    apply_tag_color_to_entry: bool | None = None
    tags: list[Tag] | None = None
    shifts: list[Shift] | None = None


class UpdateTag(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None
    color: str | None = None


class NewTag(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None
    color: str | None = None


class UpdateLocalGroup(BaseModel):
    name: str | None = None
    description: str | None = None
    members: list[str] | None = None


class NewLocalGroup(BaseModel):
    name: str | None = None
    description: str | None = None
    members: list[str] | None = None


class AuthorizationGroupManagement(BaseModel):
    add_users: list[str] | None = None
    remove_users: list[str] | None = None


class UpdateBanner(BaseModel):
    name: str | None = None
    content: str | None = None
    active: bool | None = None


class NewBanner(BaseModel):
    name: str | None = None
    content: str | None = None
    active: bool | None = None


class UpdateAuthorization(BaseModel):
    permission: PermissionType | None = None


class NewAuthorization(BaseModel):
    resource_id: str | None = None
    resource_type: ResourceType
    owner_id: str
    owner_type: OwnerType
    permission: PermissionType


class NewLogbook(BaseModel):
    name: str = Field(..., min_length=1)
    read_all: bool | None = None
    write_all: bool | None = None
    apply_tag_color_to_entry: bool | None = None


class NewEntry(BaseModel):
    logbooks: set[str] = Field(..., json_schema_extra={"uniqueItems": True})
    title: str = Field(..., min_length=1)
    text: str
    note: str | None = None
    tags: set[str] | None = Field(default=None, json_schema_extra={"uniqueItems": True})
    summarizes: Summarizes | None = None
    event_at: datetime | None = None
    user_ids_to_notify: set[str] | None = Field(
        default=None, json_schema_extra={"uniqueItems": True}
    )
    user_creator_id: str | None = None
    supersede_of: str | None = None
    important: bool | None = None


class EntryNew(BaseModel):
    """Used for follow-ups and supersedes"""

    logbooks: set[str] = Field(..., json_schema_extra={"uniqueItems": True})  # done
    title: str = Field(..., min_length=1)  # done
    text: str  # done
    note: str | None = None  # we just won't have this here
    tags: set[str] | None = Field(
        default=None, json_schema_extra={"uniqueItems": True}
    )  # done
    additional_authors: list[str] | None = None  # unused
    attachments: set[str] | None = Field(  # done
        default=None, json_schema_extra={"uniqueItems": True}
    )
    summarizes: Summarizes | None = None  # TODO: what is this?
    event_at: datetime | None = None  # done
    user_ids_to_notify: set[str] | None = Field(  # TODO
        default=None, json_schema_extra={"uniqueItems": True}
    )
    important: bool | None = None  # TODO: we use a tag instead here


class EntryImport(BaseModel):
    origin_id: str | None = None
    supersede_of_by_origin_id: str | None = None
    references_by_origin_id: list[str] | None = None
    logbooks: list[str]
    title: str = Field(..., min_length=1)
    text: str
    last_name: str | None = None
    first_name: str | None = None
    user_name: str | None = None
    note: str | None = None
    tags: list[str] | None = None
    logged_at: datetime | None = None
    event_at: datetime | None = None


class ImportEntry(BaseModel):
    """Wraps EntryImport and includes readerUserIds"""

    reader_user_ids: list[str] | None = None
    entry: EntryImport


class NewApplication(BaseModel):
    name: str
    author: str | None = None
    expiration: date


class UpdateApplication(BaseModel):
    author: str


# --- Specialized Response Payloads ---


class UserDetails(BaseModel):
    id: str | None = None
    name: str | None = None
    surname: str | None = None
    gecos: str | None = None
    email: str | None = None
    is_root: bool | None = None
    can_manage_group: bool | None = None
    authorizations: list[DetailsAuthorization] | None = None


class GroupDetails(BaseModel):
    id: str | None = None
    name: str | None = None
    description: str | None = None
    members: list[UserDetails] | None = None
    authorizations: list[DetailsAuthorization] | None = None


class Logbook(BaseModel):
    id: str | None = None
    name: str | None = None
    tags: list[Tag] | None = None
    shifts: list[Shift] | None = None
    read_all: bool | None = None
    write_all: bool | None = None
    retired: bool | None = None
    apply_tag_color_to_entry: bool | None = None
    authorizations: list[DetailsAuthorization] | None = None


class ApplicationDetails(BaseModel):
    id: str | None = None
    name: str | None = None
    author: str | None = None
    email: str | None = None
    token: str | None = None
    expiration: date | None = None
    application_managed: bool | None = None
    authorizations: list[DetailsAuthorization] | None = None


class Attachment(BaseModel):
    id: str | None = None
    file_name: str | None = None
    content_type: str | None = None
    preview_state: str | None = None
    has_webp_preview: bool | None = None
    mini_preview: bytes | None = None


class EntrySummary(BaseModel):
    id: str | None = None
    origin_id: str | None = None
    logbooks: list[LogbookSummary] | None = None
    title: str | None = None
    logged_by: str | None = None
    tags: list[Tag] | None = None
    attachments: list[Attachment] | None = None
    is_empty: bool | None = None
    shifts: list[LogbookShift] | None = None
    references: list[str] | None = None
    referenced_by: list[str] | None = None
    following_up: str | None = None
    follow_ups: list[str] | None = None
    is_supersede: bool | None = None
    note: str | None = None
    logged_at: datetime | None = None
    event_at: datetime | None = None
    important: bool | None = None


class EntrySummaryEnhanced(BaseModel):
    """Similar to EntrySummary but uses Person object for created_by and logged_by"""

    id: str | None = None
    origin_id: str | None = None
    created_by: Person | None = None
    logbooks: list[LogbookSummary] | None = None
    title: str | None = None
    tags: list[Tag] | None = None
    attachments: list[Attachment] | None = None
    is_empty: bool | None = None
    shifts: list[LogbookShift] | None = None
    references: list[str] | None = None
    referenced_by: list[str] | None = None
    following_up: str | None = None
    follow_ups: list[str] | None = None
    is_supersede: bool | None = None
    note: str | None = None
    logged_by: Person | None = None
    logged_at: datetime | None = None
    event_at: datetime | None = None
    important: bool | None = None


class Entry(BaseModel):
    id: str | None = None
    origin_id: str | None = None
    entry_type: str | None = None
    logbooks: list[LogbookSummary] | None = None
    tags: list[Tag] | None = None
    title: str | None = None
    text: str | None = None
    logged_by: str | None = None
    additional_authors: list[str] | None = None
    attachments: list[Attachment] | None = None
    follow_ups: list[EntrySummary] | None = None
    following_up: EntrySummary | None = None
    history: list[EntrySummary] | None = None
    shifts: list[LogbookShift] | None = None
    references_in_body: bool | None = None
    references: list[EntrySummary] | None = None
    referenced_by: list[EntrySummary] | None = None
    superseded_by: EntrySummary | None = None
    supersede_of: EntrySummary | None = None
    summarize_shift: str | None = None
    summary_date: datetime | None = None
    logged_at: datetime | None = None
    event_at: datetime | None = None
    important: bool | None = None


class EntryProcessingStats(BaseModel):
    processed_entries: int | None = None
    failed_entries: int | None = None
    last_updated: datetime | None = None
    completed: bool | None = None
    error_message: str | None = None


class Banner(BaseModel):
    id: str | None = None
    name: str | None = None
    content: str | None = None
    active: bool | None = None
    created_date: datetime | None = None
    created_by: str | None = None
    last_modified_date: datetime | None = None
    last_modified_by: str | None = None


class BannerLite(BaseModel):
    id: str | None = None
    name: str | None = None
    active: bool | None = None


class CacheAdminResult(BaseModel):
    all_caches_cleared: bool | None = None
    requested_cache_names: set[str] | None = Field(
        default=None, json_schema_extra={"uniqueItems": True}
    )
    cleared_cache_names: set[str] | None = Field(
        default=None, json_schema_extra={"uniqueItems": True}
    )
    missing_cache_names: set[str] | None = Field(
        default=None, json_schema_extra={"uniqueItems": True}
    )


# --- Root Wrapper Models (ApiResultResponse) ---


class BaseResponse(BaseModel):
    error_code: int
    error_message: str | None = None
    error_domain: str | None = None


class ApiResultResponseBoolean(BaseResponse):
    payload: bool | None = None


class ApiResultResponseString(BaseResponse):
    payload: str | None = None


class ApiResultResponseTag(BaseResponse):
    payload: Tag | None = None


class ApiResultResponseLogbook(BaseResponse):
    payload: Logbook | None = None


class ApiResultResponseGroupDetails(BaseResponse):
    payload: GroupDetails | None = None


class ApiResultResponseUserDetails(BaseResponse):
    payload: UserDetails | None = None


class ApiResultResponseEntry(BaseResponse):
    payload: Entry | None = None


class ApiResultResponseBanner(BaseResponse):
    payload: Banner | None = None


class ApiResultResponseAttachment(BaseResponse):
    payload: Attachment | None = None


class ApiResultResponseApplicationDetails(BaseResponse):
    payload: ApplicationDetails | None = None


class ApiResultResponseEntryProcessingStats(BaseResponse):
    payload: EntryProcessingStats | None = None


class ApiResultResponseCacheAdminResult(BaseResponse):
    payload: CacheAdminResult | None = None


class ApiResultResponseListTag(BaseResponse):
    payload: list[Tag] | None = None


class ApiResultResponseListLogbook(BaseResponse):
    payload: list[Logbook] | None = None


class ApiResultResponseListGroupDetails(BaseResponse):
    payload: list[GroupDetails] | None = None


class ApiResultResponseListUserDetails(BaseResponse):
    payload: list[UserDetails] | None = None


class ApiResultResponseListEntry(BaseResponse):
    payload: list[Entry] | None = None


class ApiResultResponseListEntrySummary(BaseResponse):
    payload: list[EntrySummary] | None = None


class ApiResultResponseListEntrySummaryEnhanced(BaseResponse):
    payload: list[EntrySummaryEnhanced] | None = None


class ApiResultResponseListBanner(BaseResponse):
    payload: list[Banner] | None = None


class ApiResultResponseListBannerLite(BaseResponse):
    payload: list[BannerLite] | None = None


class ApiResultResponseListAttachment(BaseResponse):
    payload: list[Attachment] | None = None


class ApiResultResponseListApplicationDetails(BaseResponse):
    payload: list[ApplicationDetails] | None = None
