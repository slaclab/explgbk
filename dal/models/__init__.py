"""
Pydantic models for the explgbk data access layer.

These models represent the MongoDB document schemas used throughout the application.
They are organized by domain: experiments, runs, elog, shifts, samples, files,
run tables, workflows, instruments, roles, site config, cache, and projects.
"""

from dal.models.experiments import (
    ExperimentInfo,
    ExperimentParams,
    ExperimentRegistration,
    ExperimentClone,
    ExperimentSwitch,
)
from dal.models.runs import (
    Run,
    EditableParam,
    RunStartRequest,
)
from dal.models.elog import (
    ElogAttachment,
    ElogEntry,
    ElogEntryCreate,
)
from dal.models.shifts import Shift, ShiftCreate
from dal.models.samples import Sample, CurrentSample
from dal.models.files import FileCatalogEntry, FileLocation, FileRegistration
from dal.models.run_tables import RunTable, ColumnDefinition, RunParamDescription
from dal.models.workflows import (
    WorkflowDefinition,
    WorkflowJob,
    WorkflowJobCounter,
    WorkflowDefinitionCreate,
    WorkflowJobCreate,
)
from dal.models.instruments import Instrument, InstrumentCreate
from dal.models.roles import Role
from dal.models.site_config import (
    SiteConfig,
    NamingConvention,
    FileManagerFileType,
    DmLocation,
)
from dal.models.cache import ExperimentCache, ExperimentStats, CacheRunSummary
from dal.models.projects import Project, Grid
from dal.models.kafka import KafkaEvent
from dal.models.common import PyObjectId

__all__ = [
    # Common
    "PyObjectId",
    # Experiments
    "ExperimentInfo",
    "ExperimentParams",
    "ExperimentRegistration",
    "ExperimentClone",
    "ExperimentSwitch",
    # Runs
    "Run",
    "EditableParam",
    "RunStartRequest",
    # Elog
    "ElogAttachment",
    "ElogEntry",
    "ElogEntryCreate",
    # Shifts
    "Shift",
    "ShiftCreate",
    # Samples
    "Sample",
    "CurrentSample",
    # Files
    "FileCatalogEntry",
    "FileLocation",
    "FileRegistration",
    # Run tables
    "RunTable",
    "ColumnDefinition",
    "RunParamDescription",
    # Workflows
    "WorkflowDefinition",
    "WorkflowJob",
    "WorkflowJobCounter",
    "WorkflowDefinitionCreate",
    "WorkflowJobCreate",
    # Instruments
    "Instrument",
    "InstrumentCreate",
    # Roles
    "Role",
    # Site config
    "SiteConfig",
    "NamingConvention",
    "FileManagerFileType",
    "DmLocation",
    # Cache
    "ExperimentCache",
    "ExperimentStats",
    "CacheRunSummary",
    # Projects
    "Project",
    "Grid",
    # Kafka
    "KafkaEvent",
]
