"""
Integration tests for CDC model validation against the live Kafka stream.

These tests consume the elog-v1-cdc-raw topic from offset 0 (earliest) and
validate every event through app.streaming.cdc.parse_cdc_event, asserting
that no Pydantic validation errors occur.

Prerequisites:
  - Docker Compose stack is running:
        docker compose up -d
  - Debezium has completed its initial MongoDB snapshot so the topic exists
    and contains messages.

Run with:
    uv run pytest tests/streaming/ -v -m integration

Or to also see the per-model count summary:
    uv run pytest tests/streaming/ -v -m integration -s
"""

import asyncio
import logging
from uuid import uuid4

import pytest
from faststream.kafka import KafkaBroker

from app.models.v1 import CdcEvent, CdcOp
from app.streaming.cdc import parse_cdc_event

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — override via environment or pytest CLI if needed
# ---------------------------------------------------------------------------

KAFKA_BOOTSTRAP = "localhost:9094"
CDC_TOPIC = "elog-v1-cdc-raw"

# Maximum time (seconds) for the entire drain operation regardless of activity
HARD_TIMEOUT_SEC = 120


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _drain_topic(bootstrap: str, topic: str) -> list[bytes]:
    """
    Consume all currently-available messages in *topic* starting from offset 0.

    Uses a FastStream KafkaBroker subscriber with ``auto_offset_reset="earliest"``.
    Stops precisely when every partition's position reaches its high-water mark,
    with a hard deadline as a safety net.
    """
    collected: list[bytes] = []
    drain_broker = KafkaBroker(bootstrap)
    subscriber = drain_broker.subscriber(
        topic,
        auto_offset_reset="earliest",
        group_id=f"test-cdc-validation-{uuid4().hex}",
    )

    async with drain_broker:
        await subscriber.start()
        consumer = subscriber.consumer
        partitions = consumer.assignment()
        # Wait for partition assignment
        for _ in range(40):
            partitions = consumer.assignment()
            if partitions:
                break
            await asyncio.sleep(0.25)

        end_offsets = await consumer.end_offsets(list(partitions))

        # Topic is empty
        if all(end_offsets[tp] == 0 for tp in partitions):
            await subscriber.stop()
            return collected

        deadline = asyncio.get_running_loop().time() + HARD_TIMEOUT_SEC

        while True:
            if asyncio.get_running_loop().time() > deadline:
                logger.warning(
                    "Hard timeout reached after consuming %d messages", len(collected)
                )
                break

            batch = await consumer.getmany(timeout_ms=2000, max_records=1000)
            for records in batch.values():
                for record in records:
                    collected.append(record.value)

            positions = {tp: await consumer.position(tp) for tp in partitions}
            if all(positions[tp] >= end_offsets[tp] for tp in partitions):
                break

        await subscriber.stop()

    return collected


# ---------------------------------------------------------------------------
# Module-scoped fixture — drain the topic once for all tests in this module
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
async def cdc_messages() -> list[bytes]:
    """All messages currently in the CDC topic, consumed from offset 0."""
    return await _drain_topic(KAFKA_BOOTSTRAP, CDC_TOPIC)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cdc_topic_has_messages(cdc_messages: list[bytes]) -> None:
    """
    The CDC topic must contain at least one message.

    If this test fails it usually means the Debezium initial snapshot has not
    completed yet.  Wait a minute and retry, or check the connector status:

        curl http://localhost:8083/connectors/mongodb-elog-connector/status
    """
    assert len(cdc_messages) > 0, (
        f"No messages found in {CDC_TOPIC!r}.  "
        "Ensure the Debezium connector has completed its initial snapshot."
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_all_cdc_documents_match_models(cdc_messages: list[bytes]) -> None:
    """
    Every CDC document (the 'after' field) must validate against its mapped
    Pydantic model without errors.

    The test prints a per-model count summary (visible with -s).
    """
    errors: list[str] = []
    model_counts: dict[str, int] = {}
    skip_counts: dict[str, int] = {"delete": 0, "unmapped": 0}

    for i, raw in enumerate(cdc_messages):
        try:
            event, doc = parse_cdc_event(raw)
        except Exception as exc:
            errors.append(f"[{i}] {exc!r}")
            continue

        if event.op == CdcOp.DELETE or event.after is None:
            skip_counts["delete"] += 1
            continue

        if doc is None:
            skip_counts["unmapped"] += 1
            continue

        model_name = type(doc).__name__
        model_counts[model_name] = model_counts.get(model_name, 0) + 1

    # Always log the summary — visible with -s or in captured output
    total = len(cdc_messages)
    logger.info("Consumed %d CDC messages:", total)
    logger.info("  delete / no-after : %d", skip_counts["delete"])
    logger.info("  unmapped collection: %d", skip_counts["unmapped"])
    for model, count in sorted(model_counts.items(), key=lambda x: -x[1]):
        logger.info("  %s: %d", model, count)

    if errors:
        detail = "\n  ".join(errors[:30])
        pytest.fail(
            f"{len(errors)} validation error(s) out of {total} messages:\n  {detail}"
        )
