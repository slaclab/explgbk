from typing import Any

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException

from app import crud
from app.api.deps import CurrentUser, get_current_active_superuser
from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.models import (
    Item,
    Message,
    UpdatePassword,
    User,
    UserCreate,
    UserPublic,
    UserRegister,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
)
from app.utils import generate_new_account_email, send_email

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


@router.post(
    "/", dependencies=[Depends(get_current_active_superuser)], response_model=UserPublic
)
async def create_user(*, user_in: UserCreate) -> Any:
    """
    Create new user.
    """
    user = await crud.get_user_by_email(email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )

    user = await crud.create_user(user_create=user_in)
    if settings.emails_enabled and user_in.email:
        email_data = generate_new_account_email(
            email_to=user_in.email, username=user_in.email, password=user_in.password
        )
        send_email(
            email_to=user_in.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    return user


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


@router.patch("/me/password", response_model=Message)
async def update_password_me(*, body: UpdatePassword, current_user: CurrentUser) -> Any:
    """
    Update own password.
    """
    verified, _ = verify_password(body.current_password, current_user.hashed_password)
    if not verified:
        raise HTTPException(status_code=400, detail="Incorrect password")
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=400, detail="New password cannot be the same as the current one"
        )

    current_user.hashed_password = get_password_hash(body.new_password)
    await current_user.save()
    return Message(message="Password updated successfully")


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


@router.post("/signup", response_model=UserPublic)
async def register_user(user_in: UserRegister) -> Any:
    """
    Create new user without the need to be logged in.
    """
    user = await crud.get_user_by_email(email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system",
        )

    user_create = UserCreate.model_validate(user_in.model_dump())
    return await crud.create_user(user_create=user_create)


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
