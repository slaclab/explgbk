from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException

from pief.api.routes.deps import CurrentUser, SessionDep
from pief.api.models.experiment import ExperimentPublic, ExperimentsPublic
from pief.api.models.common import Message
from pief.logdb import crud
from pief.logdb.crud import ExperimentSortField

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.get("/names", response_model=list[str])
def read_experiment_names(session: SessionDep, current_user: CurrentUser) -> list[str]:
    """Retrieve all experiment names."""
    return crud.list_experiment_names(session=session)


@router.get("/", response_model=ExperimentsPublic)
def read_experiments(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    sort_by: ExperimentSortField = "name",
    sort_desc: bool = False,
    instrument_id: UUID | None = None,
) -> Any:
    """Retrieve experiments."""
    experiments, count = crud.list_experiments(
        session=session,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_desc=sort_desc,
        instrument_id=instrument_id,
    )
    return ExperimentsPublic(
        data=[ExperimentPublic.model_validate(e) for e in experiments],
        count=count,
    )


@router.get("/{id}", response_model=ExperimentPublic)
def read_experiment(id: UUID, session: SessionDep, current_user: CurrentUser) -> Any:
    """Get experiment by ID."""
    experiment = crud.get_experiment(session=session, experiment_id=id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return ExperimentPublic.model_validate(experiment)


@router.post("/", response_model=ExperimentPublic)
def create_experiment(current_user: CurrentUser) -> Any:
    """Create new experiment."""
    raise NotImplementedError("This endpoint is not implemented yet.")


@router.put("/{id}", response_model=ExperimentPublic)
def update_experiment(id: UUID, current_user: CurrentUser) -> Any:
    """Update an experiment."""
    raise NotImplementedError("This endpoint is not implemented yet.")


@router.delete("/{id}", response_model=Message)
def delete_experiment(id: UUID, current_user: CurrentUser) -> Any:
    """Delete an experiment."""
    raise NotImplementedError("This endpoint is not implemented yet.")
