"""
v1 MongoDB document models.

Organised by MongoDB database / concern:
  - base        — shared types (PyObjectId, UTCDatetime, MongoModel)
  - site        — site database (instruments, roles, site_config, …)
  - experiment  — per-experiment databases (info, elog, runs, shifts, …)
  - debezium    — Debezium CDC event envelope
"""

from app.models.v1.base import MongoInt, MongoModel, PyObjectId, UTCDatetime
from app.models.v1.debezium import CdcEvent, CdcOp, CdcSource, UpdateDescription
from app.models.v1.experiment import (
    Counter,
    ElogAttachment,
    ElogEntry,
    ExperimentInfo,
    ExperimentRole,
    FileCatalogEntry,
    FileLocation,
    Run,
    RunParamDescription,
    Shift,
    Subscriber,
    WorkflowDefinition,
    WorkflowJob,
    WorkflowJobCounter,
)
from app.models.v1.site import (
    DmLocation,
    ExperimentSwitch,
    ExperimentSwitchNotification,
    FileTypeConfig,
    Instrument,
    InstrumentParamDescription,
    InstrumentRole,
    RunTable,
    RunTableColDef,
    SiteConfig,
    SiteLog,
    SiteRole,
)

__all__ = [
    # base
    "MongoInt",
    "MongoModel",
    "PyObjectId",
    "UTCDatetime",
    # site
    "DmLocation",
    "ExperimentSwitch",
    "ExperimentSwitchNotification",
    "FileTypeConfig",
    "Instrument",
    "InstrumentParamDescription",
    "InstrumentRole",
    "RunTable",
    "RunTableColDef",
    "SiteConfig",
    "SiteLog",
    "SiteRole",
    # experiment
    "Counter",
    "ElogAttachment",
    "ElogEntry",
    "ExperimentInfo",
    "ExperimentRole",
    "FileCatalogEntry",
    "FileLocation",
    "Run",
    "RunParamDescription",
    "Shift",
    "Subscriber",
    "WorkflowDefinition",
    "WorkflowJob",
    "WorkflowJobCounter",
    # debezium
    "CdcEvent",
    "CdcOp",
    "CdcSource",
    "UpdateDescription",
]
