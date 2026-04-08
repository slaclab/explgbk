from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from pief.logdb import crud
from pief.api.routes.deps import CurrentUser, SessionDep, get_current_active_superuser
from pief.api.models.common import Message
from pief.api.models.user import UserPublic, UsersPublic, UserUpdateMe
from pief.logdb.schemas import UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UsersPublic,
)
def read_users(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """Retrieve users."""
    users, count = crud.list_users(session=session, skip=skip, limit=limit)
    return UsersPublic(
        data=[UserPublic.model_validate(u) for u in users],
        count=count,
    )


@router.patch("/me", response_model=UserPublic)
def update_user_me(
    session: SessionDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> Any:
    """Update own user."""
    user_update = UserUpdate(**user_in.model_dump(exclude_unset=True))
    updated = crud.update_user(session=session, user=current_user, user_update=user_update)
    session.commit()
    return UserPublic.model_validate(updated)


@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> Any:
    """Get current user."""
    return UserPublic.model_validate(current_user)


@router.delete("/me", response_model=Message)
def delete_user_me(session: SessionDep, current_user: CurrentUser) -> Any:
    """Delete own user."""
    crud.delete_user(session=session, user=current_user)
    session.commit()
    return Message(message="User deleted successfully")


@router.get("/{user_id}", response_model=UserPublic)
def read_user_by_id(
    user_id: UUID, session: SessionDep, current_user: CurrentUser
) -> Any:
    """Get a specific user by id."""
    user = crud.get_user(session=session, user_id=user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserPublic.model_validate(user)


@router.patch(
    "/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
)
def update_user(user_id: UUID, session: SessionDep, user_in: UserUpdate) -> Any:
    """Update a user (superuser only)."""
    db_user = crud.get_user(session=session, user_id=user_id)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="The user with this id does not exist in the system",
        )
    return UserPublic.model_validate(
        crud.update_user(session=session, user=db_user, user_update=user_in)
    )


@router.delete(
    "/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=Message,
)
def delete_user(user_id: UUID, session: SessionDep, current_user: CurrentUser) -> Any:
    """Delete a user."""
    user = crud.get_user(session=session, user_id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    crud.delete_user(session=session, user=user)
    session.commit()
    return Message(message="User deleted successfully")
