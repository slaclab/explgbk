from fastapi import APIRouter

from pief.logdb import crud
from pief.api.routes.deps import CurrentUser, SessionDep
from pief.api.models.experiment import InstrumentSummary

router = APIRouter(prefix="/instruments", tags=["instruments"])


@router.get("/", response_model=list[InstrumentSummary])
def read_instruments(
    session: SessionDep, current_user: CurrentUser
) -> list[InstrumentSummary]:
    """Return each distinct instrument_id with the count of experiments under it."""
    results = crud.list_instrument_experiment_counts(session=session)
    return [
        InstrumentSummary(instrument_id=r[0], experiment_count=r[1]) for r in results
    ]
