from typing import Any

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException

from app import crud
from app.api.deps import CurrentUser, get_current_active_superuser
from app.models.common import Message
from app.models.item import Item
from app.models.user import User, UserPublic, UsersPublic, UserUpdate, UserUpdateMe

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UsersPublic,
)
async def read_users(skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve users.
    """
    count = await User.find_all().count()
    users = await User.find_all().sort("-created_at").skip(skip).limit(limit).to_list()
    return UsersPublic(
        data=[UserPublic.model_validate(user, from_attributes=True) for user in users],
        count=count,
    )


@router.patch("/me", response_model=UserPublic)
async def update_user_me(*, user_in: UserUpdateMe, current_user: CurrentUser) -> Any:
    """
    Update own user.
    """
    if user_in.email:
        existing_user = await crud.get_user_by_email(email=user_in.email)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )

    user_data = user_in.model_dump(exclude_unset=True)
    await current_user.set(user_data)
    return current_user


@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> Any:
    """
    Get current user.
    """
    return current_user


@router.delete("/me", response_model=Message)
async def delete_user_me(current_user: CurrentUser) -> Any:
    """
    Delete own user.
    """
    if current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    await Item.find(Item.owner_id == current_user.id).delete()
    await current_user.delete()
    return Message(message="User deleted successfully")


@router.get("/{user_id}", response_model=UserPublic)
async def read_user_by_id(user_id: PydanticObjectId, current_user: CurrentUser) -> Any:
    """
    Get a specific user by id.
    """
    user = await User.get(user_id)
    if user == current_user:
        return user
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="The user doesn't have enough privileges",
        )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch(
    "/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
)
async def update_user(*, user_id: PydanticObjectId, user_in: UserUpdate) -> Any:
    """
    Update a user.
    """
    db_user = await User.get(user_id)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="The user with this id does not exist in the system",
        )
    if user_in.email:
        existing_user = await crud.get_user_by_email(email=user_in.email)
        if existing_user and existing_user.id != db_user.id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )

    return await crud.update_user(db_user=db_user, user_in=user_in)


@router.delete("/{user_id}", dependencies=[Depends(get_current_active_superuser)])
async def delete_user(current_user: CurrentUser, user_id: PydanticObjectId) -> Message:
    """
    Delete a user.
    """
    user = await User.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user == current_user:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )

    await Item.find(Item.owner_id == user.id).delete()
    await user.delete()
    return Message(message="User deleted successfully")
