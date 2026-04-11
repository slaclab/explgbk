from typing import Any, Literal

from beanie.odm.operators.find.comparison import In
from fastapi import APIRouter
from pydantic import BaseModel
from pymongo import AsyncMongoClient

from app.api.deps import CurrentUser, MongoClientDep
from app.models.cache import Experiment, ExperimentPublic, ExperimentsPublic
from app.models.common import Message
from app.models.experiment import ExperimentInfo, ExperimentRole

router = APIRouter(prefix="/experiments", tags=["experiments"])

_COLLECTION_INFO = "info"
_COLLECTION_ROLES = "roles"


async def _get_experiment_info(
    mongo: AsyncMongoClient, experiment_id: str
) -> ExperimentInfo | None:
    raw = await mongo[experiment_id][_COLLECTION_INFO].find_one({"_id": experiment_id})
    if raw is None:
        return None
    return ExperimentInfo.model_validate(raw)


async def _get_experiment_roles(
    mongo: AsyncMongoClient, experiment_id: str
) -> list[ExperimentRole]:
    raw_docs = await mongo[experiment_id][_COLLECTION_ROLES].find({}).to_list()
    return [ExperimentRole.model_validate(doc) for doc in raw_docs]


class _NameProjection(BaseModel):
    name: str


@router.get("/names", response_model=list[str])
async def read_experiment_names(current_user: CurrentUser) -> list[str]:
    """
    Retrieve all experiment names.
    """
    if current_user.is_superuser:
        results = await Experiment.find_all().project(_NameProjection).to_list()
    else:
        user_key = f"uid:{current_user.email}"
        results = (
            await Experiment.find(In(Experiment.players, [user_key]))
            .project(_NameProjection)
            .to_list()
        )
    return [r.name for r in results]


ExperimentSortField = Literal[
    "name",
    "instrument",
    "leader_account",
    "run_count",
    "start_time",
    "created_at",
]


@router.get("/", response_model=ExperimentsPublic)
async def read_experiments(
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    sort_by: ExperimentSortField = "name",
    sort_desc: bool = False,
    instrument: str | None = None,
) -> ExperimentsPublic:
    """
    Retrieve experiments. Superusers see all; others see only experiments
    where they are listed as a player.
    """
    sort_key = f"-{sort_by}" if sort_desc else f"+{sort_by}"
    instrument_filter = (Experiment.instrument == instrument,) if instrument else ()
    if current_user.is_superuser:
        query = Experiment.find(*instrument_filter)
        count = await query.count()
        experiments = await query.sort(sort_key).skip(skip).limit(limit).to_list()
    else:
        user_key = f"uid:{current_user.email}"
        query = Experiment.find(In(Experiment.players, [user_key]), *instrument_filter)
        count = await query.count()
        experiments = await query.sort(sort_key).skip(skip).limit(limit).to_list()

    return ExperimentsPublic(
        data=[
            ExperimentPublic.model_validate(exp, from_attributes=True)
            for exp in experiments
        ],
        count=count,
    )


@router.get("/{id}", response_model=ExperimentPublic)
async def read_experiment(
    id: str, current_user: CurrentUser, mongo: MongoClientDep
) -> ExperimentPublic:
    """
    Get experiment by ID (name). Reads directly from the per-experiment database.
    """
    raise NotImplementedError("This endpoint is not implemented yet.")


@router.post("/", response_model=ExperimentPublic)
async def create_experiment(*, current_user: CurrentUser) -> Any:
    """
    Create new experiment.
    """
    raise NotImplementedError("This endpoint is not implemented yet.")


@router.put("/{id}", response_model=ExperimentPublic)
async def update_experiment(
    *,
    current_user: CurrentUser,
    id: str,
) -> Any:
    """
    Update an experiment.
    """
    raise NotImplementedError("This endpoint is not implemented yet.")


@router.delete("/{id}")
async def delete_experiment(current_user: CurrentUser, id: str) -> Message:
    """
    Delete an experiment.
    """
    raise NotImplementedError("This endpoint is not implemented yet.")
