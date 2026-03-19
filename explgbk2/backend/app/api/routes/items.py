from typing import Any

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser
from app.models import Item, ItemCreate, ItemPublic, ItemsPublic, ItemUpdate, Message

router = APIRouter(prefix="/items", tags=["items"])


@router.get("/", response_model=ItemsPublic)
async def read_items(current_user: CurrentUser, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve items.
    """
    if current_user.is_superuser:
        count = await Item.find_all().count()
        items = (
            await Item.find_all().sort("-created_at").skip(skip).limit(limit).to_list()
        )
    else:
        count = await Item.find(Item.owner_id == current_user.id).count()
        items = (
            await Item.find(Item.owner_id == current_user.id)
            .sort("-created_at")
            .skip(skip)
            .limit(limit)
            .to_list()
        )

    return ItemsPublic(
        data=[ItemPublic.model_validate(item, from_attributes=True) for item in items],
        count=count,
    )


@router.get("/{id}", response_model=ItemPublic)
async def read_item(current_user: CurrentUser, id: PydanticObjectId) -> Any:
    """
    Get item by ID.
    """
    item = await Item.get(id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return item


@router.post("/", response_model=ItemPublic)
async def create_item(*, current_user: CurrentUser, item_in: ItemCreate) -> Any:
    """
    Create new item.
    """
    if current_user.id is None:
        raise HTTPException(status_code=400, detail="User not found")

    item = Item(**item_in.model_dump(), owner_id=current_user.id)
    await item.insert()
    return item


@router.put("/{id}", response_model=ItemPublic)
async def update_item(
    *,
    current_user: CurrentUser,
    id: PydanticObjectId,
    item_in: ItemUpdate,
) -> Any:
    """
    Update an item.
    """
    item = await Item.get(id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    update_dict = item_in.model_dump(exclude_unset=True)
    await item.set(update_dict)
    return item


@router.delete("/{id}")
async def delete_item(current_user: CurrentUser, id: PydanticObjectId) -> Message:
    """
    Delete an item.
    """
    item = await Item.get(id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    await item.delete()
    return Message(message="Item deleted successfully")
