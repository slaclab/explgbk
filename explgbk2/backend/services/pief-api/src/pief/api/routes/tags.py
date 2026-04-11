from typing import Any

from fastapi import APIRouter

from pief.api.models.tag import TagPublic, TagsPublic
from pief.api.routes.deps import CurrentUser, SessionDep
from pief.logdb import crud

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("/", response_model=TagsPublic)
async def read_tags(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """List all tags."""
    tags, count = await crud.list_tags(session=session, skip=skip, limit=limit)
    return TagsPublic(
        data=[TagPublic.model_validate(t) for t in tags],
        count=count,
    )
