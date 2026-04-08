"""
FastStream CDC event consumer for the elog-v1-cdc-raw Kafka topic.

The Debezium MongoDB connector routes all collection changes from every
database to a single raw topic.  This module defines:

  - COLLECTION_MODEL_MAP  — maps (db, collection) to a Pydantic document model
  - get_model_for_event() — resolves the right model for a CdcEvent
  - parse_cdc_event()     — parses raw bytes → (CdcEvent, validated doc | None)
  - broker / app          — the FastStream KafkaBroker and FastStream app

The `parse_cdc_event` function is intentionally kept free of FastStream
coupling so it can be called directly in tests without starting the broker.
"""

import logging
from typing import TypeVar

from faststream import FastStream, Logger
from faststream.kafka import KafkaBroker
from pydantic import BaseModel


from pief.models.legacy import (
    CdcEvent,
    CdcOp,
    Counter,
    ElogEntry,
    ExperimentInfo,
    ExperimentRole,
    ExperimentSwitch,
    ExperimentSwitchNotification,
    FileCatalogEntry,
    Instrument,
    InstrumentParamDescription,
    Run,
    RunParamDescription,
    RunTable,
    Shift,
    SiteConfig,
    SiteLog,
    SiteRole,
    Subscriber,
    WorkflowDefinition,
    WorkflowJob,
)
from pief.streams.config import settings

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Collection → model dispatch table
# ---------------------------------------------------------------------------

# Keys are (db_name, collection_name).  The special db_name "*" matches any
# experiment database (i.e., databases that are not in KNOWN_SPECIFIC_DBS).
COLLECTION_MODEL_MAP: dict[tuple[str, str], type] = {
    # site database
    ("site", "instruments"): Instrument,
    ("site", "roles"): SiteRole,
    ("site", "site_config"): SiteConfig,
    ("site", "experiment_switch"): ExperimentSwitch,
    ("site", "experiment_switch_notifications"): ExperimentSwitchNotification,
    ("site", "run_tables"): RunTable,
    ("site", "instrument_param_descriptions"): InstrumentParamDescription,
    ("site", "logs"): SiteLog,
    # per-experiment collections (wildcard db)
    ("*", "info"): ExperimentInfo,
    ("*", "roles"): ExperimentRole,
    ("*", "elog"): ElogEntry,
    ("*", "runs"): Run,
    ("*", "shifts"): Shift,
    ("*", "file_catalog"): FileCatalogEntry,
    ("*", "workflow_definitions"): WorkflowDefinition,
    ("*", "workflow_jobs"): WorkflowJob,
    ("*", "run_param_descriptions"): RunParamDescription,
    ("*", "run_tables"): RunTable,
    ("*", "counters"): Counter,
    ("*", "subscribers"): Subscriber,
}

# Database that has explicit entries in COLLECTION_MODEL_MAP.
# Any db other than this is treated as a per-experiment database.
SITE_DB: str = "site"


def get_model_for_event(event: CdcEvent) -> type | None:
    """
    Return the Pydantic document model class for a CDC event.

    Returns None if the (db, collection) combination is not in the dispatch
    table (e.g. gridfs or unknown collections).
    """
    db = event.source.db
    collection = event.source.collection

    # Prefer a specific (db, collection) entry
    if (db, collection) in COLLECTION_MODEL_MAP:
        return COLLECTION_MODEL_MAP[(db, collection)]

    # For experiment databases, fall back to the wildcard entry
    if db != SITE_DB:
        return COLLECTION_MODEL_MAP.get(("*", collection))

    return None


def parse_cdc_event(raw: bytes) -> tuple[CdcEvent, T | None]:
    """
    Parse a raw Kafka CDC message into a (CdcEvent, document) pair.

    The Debezium connector is configured with ``value.converter.schemas.enable=false``
    so messages are plain CdcEvent JSON with no Kafka Connect schema envelope.

    The document is the validated Pydantic model instance built from the
    'after' field of the change event.  It is None when the operation is a
    delete (no 'after' document).

    Raises ValueError if the (db, collection) has no mapped model.
    Raises pydantic.ValidationError if the event or document fields fail validation.
    """
    event = CdcEvent.model_validate_json(raw)

    # Deletes and truncates carry no 'after' document
    if event.op == CdcOp.DELETE or event.after is None:
        return event, None

    model_cls = get_model_for_event(event)
    if model_cls is None:
        raise ValueError(
            f"No model mapped for db={event.source.db!r} collection={event.source.collection!r}"
        )

    return event, model_cls.model_validate_json(event.after)


# ---------------------------------------------------------------------------
# FastStream application
# ---------------------------------------------------------------------------

broker = KafkaBroker(settings.KAFKA_BOOTSTRAP_SERVERS)


app = FastStream(broker)


@broker.subscriber(settings.CDC_TOPIC, batch=True, max_records=500)
async def handle_cdc_event(msgs: list[bytes], logger: Logger) -> None:
    """
    Consume a batch of raw Debezium CDC events, parse each one, and validate
    the document against the appropriate Pydantic model.
    """
    for raw in msgs:
        event, doc = parse_cdc_event(raw)
        logger.debug(
            "CDC op=%s db=%s col=%s model=%s",
            event.op,
            event.source.db,
            event.source.collection,
            type(doc).__name__ if doc is not None else "None",
        )
