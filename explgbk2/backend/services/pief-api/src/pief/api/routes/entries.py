from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException

from pief.api.models.entry import (
    EntryCreate,
    EntryPublic,
    EntryRevisionPublic,
    EntryUpdate,
)
from pief.api.routes.deps import CurrentUser, SessionDep
from pief.logdb import crud
from pief.logdb.schemas import EntryCreate as DBEntryCreate
from pief.logdb.schemas import EntryUpdate as DBEntryUpdate

router = APIRouter(prefix="/entries", tags=["entries"])


@router.post("/", response_model=EntryPublic, status_code=201)
async def create_entry(
    body: EntryCreate, session: SessionDep, current_user: CurrentUser
) -> Any:
    """Create a new logbook entry."""
    user = await crud.get_user_by_username(session=session, username=body.username)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    db_entry_in = DBEntryCreate(
        author_id=user.id,
        title=body.title,
        content=body.content,
        content_type=body.content_type,
        occurred_at=body.occurred_at,
        root_id=body.root_id,
        run_id=body.run_id,
        shift_id=body.shift_id,
        logbook_ids=list(body.logbook_ids),
        tag_ids=list(body.tag_ids),
    )
    entry = await crud.create_entry(session=session, entry_in=db_entry_in)
    await session.commit()
    entry = await crud.get_entry_full(session=session, entry_id=entry.id)
    return EntryPublic.model_validate(entry)


@router.get("/{entry_id}", response_model=EntryPublic)
async def read_entry(
    entry_id: UUID, session: SessionDep, current_user: CurrentUser
) -> Any:
    """Get a single entry by ID."""
    entry = await crud.get_entry_full(session=session, entry_id=entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    return EntryPublic.model_validate(entry)


@router.patch("/{entry_id}", response_model=EntryPublic)
async def update_entry(
    entry_id: UUID, body: EntryUpdate, session: SessionDep, current_user: CurrentUser
) -> Any:
    """Update an entry's content or tags."""
    entry = await crud.get_entry(session=session, entry_id=entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    db_update = DBEntryUpdate(
        title=body.title,
        content=body.content,
        occurred_at=body.occurred_at,
        tag_ids=list(body.tag_ids) if body.tag_ids is not None else None,
    )
    await crud.update_entry(session=session, entry=entry, entry_update=db_update)
    await session.commit()
    entry = await crud.get_entry_full(session=session, entry_id=entry_id)
    return EntryPublic.model_validate(entry)


@router.delete("/{entry_id}", status_code=204)
async def delete_entry(
    entry_id: UUID, session: SessionDep, current_user: CurrentUser
) -> None:
    """Retract an entry."""
    entry = await crud.get_entry(session=session, entry_id=entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    await crud.retract_entry(session=session, entry=entry, retracted_by=current_user.id)
    await session.commit()


@router.get("/{entry_id}/revisions", response_model=list[EntryRevisionPublic])
async def read_entry_revisions(
    entry_id: UUID, session: SessionDep, current_user: CurrentUser
) -> Any:
    """List all revisions for an entry."""
    entry = await crud.get_entry(session=session, entry_id=entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    revisions = await crud.get_entry_revisions(session=session, entry_id=entry_id)
    return [EntryRevisionPublic.model_validate(r) for r in revisions]


@router.get("/{entry_id}/thread", response_model=list[EntryPublic])
async def read_entry_thread(
    entry_id: UUID, session: SessionDep, current_user: CurrentUser
) -> Any:
    """List thread replies for an entry."""
    entry = await crud.get_entry(session=session, entry_id=entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    replies = await crud.get_thread_replies_full(session=session, root_id=entry_id)
    return [EntryPublic.model_validate(r) for r in replies]
