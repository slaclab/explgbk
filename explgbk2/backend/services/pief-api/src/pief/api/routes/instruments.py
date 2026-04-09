from fastapi import APIRouter

from pief.api.routes.deps import CurrentUser, SessionDep
from pief.api.models.experiment import InstrumentSummary

router = APIRouter(prefix="/instruments", tags=["instruments"])


@router.get("/", response_model=list[InstrumentSummary])
async def read_instruments(
    session: SessionDep, current_user: CurrentUser
) -> list[InstrumentSummary]:
    """Return each distinct instrument_id that has at least one experiment."""
    raise NotImplementedError("This route is not yet implemented.")
