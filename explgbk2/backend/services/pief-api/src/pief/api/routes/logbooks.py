from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException

from pief.api.models.entry import EntriesPublic, EntryPublic
from pief.api.models.logbook import LogbookPublic, LogbooksPublic
from pief.api.routes.deps import CurrentUser, SessionDep
from pief.logdb import crud
from pief.models.v1.entries import LogbookType

router = APIRouter(prefix="/logbooks", tags=["logbooks"])


@router.get("/", response_model=LogbooksPublic)
async def read_logbooks(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    type: LogbookType | None = None,
) -> Any:
    """List all logbooks, optionally filtered by type."""
    logbooks, count = await crud.list_logbooks(
        session=session, skip=skip, limit=limit, type=type
    )
    return LogbooksPublic(
        data=[LogbookPublic.model_validate(lb) for lb in logbooks],
        count=count,
    )


@router.get("/{logbook_id}/entries", response_model=EntriesPublic)
async def read_logbook_entries(
    logbook_id: UUID,
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    tag_id: UUID | None = None,
    run_id: UUID | None = None,
) -> Any:
    """List entries for a logbook with optional tag/run filters."""
    logbook = await crud.get_logbook(session=session, logbook_id=logbook_id)
    if logbook is None:
        raise HTTPException(status_code=404, detail="Logbook not found")
    entries, count = await crud.list_logbook_entries(
        session=session,
        logbook_id=logbook_id,
        skip=skip,
        limit=limit,
        tag_id=tag_id,
        run_id=run_id,
    )
    return EntriesPublic(
        data=[EntryPublic.model_validate(e) for e in entries],
        count=count,
    )
