# DAL Pydantic Models

Pydantic v2 models representing the MongoDB document schemas used throughout `explgbk`.

## Background

The existing codebase uses raw dictionaries everywhere — function signatures accept and return `dict[str, Any]`, MongoDB documents are passed around untyped, and validation is done ad-hoc with `necessary_keys - info.keys()` checks. These models are the first step toward structured data throughout the backend.

## File overview

| File | Models | Description |
|---|---|---|
| `common.py` | `PyObjectId`, `MongoBaseModel` | BSON ObjectId type + shared base config |
| `experiments.py` | `ExperimentInfo`, `ExperimentParams`, `ExperimentRegistration`, `ExperimentClone`, `ExperimentSwitch` | Experiment metadata, registration, and instrument switching |
| `runs.py` | `Run`, `EditableParam`, `RunStartRequest` | Run documents with DAQ params and user-editable params |
| `elog.py` | `ElogEntry`, `ElogAttachment`, `ElogEntryCreate` | Logbook entries with threading, attachments, versioning |
| `shifts.py` | `Shift`, `ShiftCreate` | Shift scheduling |
| `samples.py` | `Sample`, `CurrentSample` | Sample tracking (with `extra="allow"` for modal params) |
| `files.py` | `FileCatalogEntry`, `FileLocation`, `FileRegistration` | File catalog with multi-location tracking |
| `run_tables.py` | `RunTable`, `ColumnDefinition`, `RunParamDescription` | Configurable tabular views of run data |
| `workflows.py` | `WorkflowDefinition`, `WorkflowJob`, `WorkflowJobCounter`, `WorkflowDefinitionCreate`, `WorkflowJobCreate` | Workflow automation definitions and jobs |
| `instruments.py` | `Instrument`, `InstrumentCreate` | Instrument configuration |
| `roles.py` | `Role` | Access control roles (per-experiment and site-level) |
| `site_config.py` | `SiteConfig`, `NamingConvention`, `FileManagerFileType`, `DmLocation` | Site-wide configuration |
| `cache.py` | `ExperimentCache`, `ExperimentStats`, `CacheRunSummary`, `CacheFileTimestamps`, `CachePocFeedback`, `DailyBreakdown` | Denormalized cache for fast listing/search |
| `projects.py` | `Project`, `Grid` | CryoEM sample prep projects and grids |
| `kafka.py` | `KafkaEvent` | Standard Kafka event envelope |

## How models were derived

The codebase has no formal schema definitions. Models were reverse-engineered by reading:

1. **DAL layer** (`dal/explgbk.py`, `dal/run_control.py`, `dal/exp_cache.py`) — every `insert_one`, `find_one_and_update`, `$set`, and aggregation pipeline to see what fields are written and read.
2. **Service layer** (`services/explgbk.py`) — the `necessary_keys` validation blocks that act as informal schemas for API request bodies, plus the `request.json` and `request.args` parsing.
3. **MongoDB collection patterns** — the one-database-per-experiment architecture, the `site` and `explgbk_cache` global databases, and the `lgbkprjs` project database.
4. **Kafka event publishing** — the `context.kafka_producer.send()` calls that show the event envelope shape.

## Design decisions

- **`MongoBaseModel`** sets `arbitrary_types_allowed=True` (for `ObjectId`) and `populate_by_name=True` (so both `_id` and `id` work).
- **`PyObjectId`** is an annotated type that accepts both `bson.ObjectId` instances and valid hex strings, making it easy to construct models from either MongoDB documents or JSON API input.
- **`extra="allow"`** is set on models whose documents accept arbitrary additional fields: `Sample`, `Project`, `Grid`, `WorkflowDefinition`, `WorkflowJob`, `SiteConfig`, `DmLocation`, and `ExperimentParams`. These extra fields come from modal param configs (JSON files in `static/json/`) or external integrations.
- **Separate "Create" models** (e.g. `ElogEntryCreate`, `ShiftCreate`, `RunStartRequest`) represent API request bodies and omit server-set fields like `_id`, `insert_time`, `author`.
- **Computed fields** like `Run.duration`, `Shift.logical_end_time`, and `Sample.current` are `Optional` with `None` defaults because they are added by the DAL on read, not stored in MongoDB.
- **`num: int | str`** appears on `Run`, `WorkflowJob`, `FileCatalogEntry`, and `Grid` because CryoEM experiments use string-based grid numbers instead of integer run numbers.
- **Aliases** map Python-idiomatic field names to MongoDB keys (e.g. `id` -> `_id`, `total_data_size` -> `totalDataSize`, `crud` -> `CRUD`).

## Known uncertainties

These are flagged with comments in the code:

- **`WorkflowJob.status`** — observed values include `"START"`, `"RUNNING"`, `"DONE"`, `"FAILED"` but the full set depends on the external JID/ARP integration and may include others.
- **`RunTable.table_type`** — observed `"generatedtable"` and `"generatedscatter"`; there may be other types.
- **`ColumnDefinition.type`** — categorizes column source (e.g. `"run_info"`, `"EPICS/..."`, `"Editables"`) but exact values are not enumerated in code.
- **`ExperimentParams`** — the keys are highly variable per experiment. The named fields (`DATA_PATH`, `PNR`, etc.) are common but far from exhaustive.
- **`WorkflowDefinition`** extra fields — workflow definitions carry arbitrary ARP/JID-specific fields that vary by deployment.
- **`SiteConfig`** — the actual document may contain fields not yet captured here.

## Next steps

These models are not yet applied to the backend code. Planned integration:

1. Type DAL function signatures to accept/return models instead of `dict[str, Any]`.
2. Replace `necessary_keys` validation in the service layer with Pydantic model validation.
3. Use models for Kafka event serialization/deserialization.
4. Consider adding `model_serializer` methods for MongoDB-compatible output (handling `ObjectId` and `datetime`).
