"""
Models for workflow definitions and jobs.

Workflow definitions specify automated processing triggered by run events.
Workflow jobs track individual executions of those definitions.
"""

from typing import Any

from pydantic import Field

from dal.models.common import MongoBaseModel, PyObjectId


class WorkflowDefinition(MongoBaseModel):
    """
    A workflow definition from the `workflow_definitions` collection.

    NOTE: Beyond the required fields, workflow definitions can carry
    arbitrary additional fields specific to the ARP/JID integration
    layer (e.g. batch parameters, environment variables). The
    `extra="allow"` setting accommodates this.
    """

    id: PyObjectId | None = Field(None, alias="_id")
    name: str
    executable: str | None = None
    trigger: str | None = None
    location: str | None = None
    parameters: str | None = None
    run_as_user: str | None = None

    model_config = {"extra": "allow"}


class WorkflowJobCounter(MongoBaseModel):
    """
    A progress counter displayed for a running workflow job.

    NOTE: The label and value fields may contain HTML fragments
    (e.g. "<b>Events</b>").
    """

    label: str
    value: str


class WorkflowJob(MongoBaseModel):
    """
    A workflow job document from the `workflow_jobs` collection.

    NOTE: The `status` field values are not fully enumerated. Observed
    values include "START", "RUNNING", "DONE", "FAILED" but there may
    be others depending on the JID/ARP integration.
    """

    id: PyObjectId | None = Field(None, alias="_id")
    run_num: int | str
    def_id: PyObjectId | None = None
    user: str | None = None
    status: str | None = None
    tool_id: str | None = None
    log_file_path: str | None = None
    counters: list[WorkflowJobCounter] = Field(default_factory=list)
    # Populated via aggregation on read, not stored directly
    definition: dict[str, Any] | None = Field(None, alias="def")
    experiment: str | None = None

    model_config = {"extra": "allow"}


class WorkflowDefinitionCreate(MongoBaseModel):
    """
    Request model for creating/updating a workflow definition.
    """

    name: str
    executable: str
    trigger: str
    location: str
    parameters: str

    model_config = {"extra": "allow"}


class WorkflowJobCreate(MongoBaseModel):
    """
    Request model for submitting a new workflow job.
    """

    job_name: str
    run_num: int | str
