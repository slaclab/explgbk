"""
Pydantic v2 models for Debezium MongoDB CDC events.

The Debezium MongoDB connector publishes change events to Kafka.
In this deployment all collections are routed to a single topic:
  elog-v1-cdc-raw

Message structure:

  {
    "before": null | "<MongoDB extended JSON string>",
    "after":  null | "<MongoDB extended JSON string>",
    "patch":  null | "<update document string>",
    "filter": null | "<filter string>",
    "updateDescription": {
        "updatedFields": "<JSON string of changed fields>",
        "removedFields": ["field", ...],
        "truncatedArrays": [...]
    } | null,
    "source": {
        "version": "...",
        "connector": "mongodb",
        "name": "elog-v1-cdc",
        "ts_ms": <epoch ms>,
        "snapshot": "true" | "false" | "last",
        "db": "<database>",
        "rs": "rs0",
        "collection": "<collection>",
        "ord": <int>,
        "lsid": null | "...",
        "txnNumber": null | <int>,
        "wallTime": <epoch ms>
    },
    "op": "c" | "u" | "d" | "r",
    "ts_ms": <epoch ms>,
    "transaction": null
  }

The `before` / `after` fields are strings containing the full MongoDB document
serialised as MongoDB Extended JSON v2.  Parse them with json.loads() and then
pass the resulting dict to the appropriate document model (e.g. ElogEntry).
"""

from enum import StrEnum

from pydantic import Field

from app.models.v1.base import MongoModel

# ---------------------------------------------------------------------------
# Nested models
# ---------------------------------------------------------------------------


class CdcSource(MongoModel):
    """Source metadata block present in every CDC event."""

    version: str
    connector: str
    name: str
    ts_ms: int
    snapshot: str | None = None
    db: str
    rs: str | None = None
    collection: str
    ord: int | None = None
    lsid: str | None = None
    txn_number: int | None = Field(default=None, alias="txnNumber")
    wall_time: int | None = Field(default=None, alias="wallTime")


class UpdateDescription(MongoModel):
    """
    Present on update (op="u") events.

    updated_fields is a JSON string of the fields that changed.
    removed_fields lists field names that were unset.
    """

    updated_fields: str | None = Field(default=None, alias="updatedFields")
    removed_fields: list[str] | None = Field(default=None, alias="removedFields")
    truncated_arrays: list | None = Field(default=None, alias="truncatedArrays")


# ---------------------------------------------------------------------------
# Top-level CDC event
# ---------------------------------------------------------------------------


class CdcOp(StrEnum):
    CREATE = "c"
    UPDATE = "u"
    DELETE = "d"
    READ = "r"  # snapshot


class CdcEvent(MongoModel):
    """
    Top-level Debezium MongoDB change event.

    `before` and `after` are raw MongoDB Extended JSON strings.
    """

    before: str | None = None
    after: str | None = None
    patch: str | None = None
    filter: str | None = None
    update_description: UpdateDescription | None = Field(
        default=None, alias="updateDescription"
    )
    source: CdcSource
    op: CdcOp
    ts_ms: int
    transaction: None = None
