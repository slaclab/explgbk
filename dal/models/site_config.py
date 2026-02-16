"""
Models for site-wide configuration.

The site config is a single document in `site.site_config` that controls
naming conventions, file type definitions, and data management locations.
"""

from pydantic import BaseModel, Field

from dal.models.common import MongoBaseModel, PyObjectId


class NamingConvention(BaseModel):
    """
    A naming convention rule for a specific entity field.

    NOTE: These are loaded from site_config and drive the UI form
    placeholders and validation.
    """

    placeholder: str = ""
    tooltip: str = ""
    validation_regex: str = ""


class FileManagerFileType(BaseModel):
    """
    A file type definition for the file manager UI.
    """

    name: str
    label: str
    tooltip: str = ""
    patterns: list[str] = Field(default_factory=list)
    selected: bool = False


class DmLocation(BaseModel):
    """
    A data management location (e.g. NERSC, SLAC).

    NOTE: The JID fields (jid_client_key, jid_client_cert, jid_ca_cert,
    jid_prefix) are not always present. Their presence depends on whether
    the location supports workflow job submission.
    """

    name: str
    all_experiments: bool = False
    jid_client_key: str | None = None
    jid_client_cert: str | None = None
    jid_ca_cert: str | None = None
    jid_prefix: str | None = None

    model_config = {"extra": "allow"}


class SiteConfig(MongoBaseModel):
    """
    The single site configuration document from `site.site_config`.

    NOTE: This model captures the known fields, but the actual document
    may contain additional fields not yet modeled here. The `extra="allow"`
    setting accommodates this.
    """

    id: PyObjectId | None = Field(None, alias="_id")
    naming_conventions: dict[str, NamingConvention] = Field(default_factory=dict)
    filemanager_file_types: dict[str, FileManagerFileType] = Field(default_factory=dict)
    dm_locations: list[DmLocation] = Field(default_factory=list)
    dm_mover_prefix: str | None = None
    experiment_spanning_elogs: list[str] = Field(default_factory=list)

    model_config = {"extra": "allow"}
