from app import crud
from app.models import Item, ItemCreate
from tests.utils.user import create_random_user
from tests.utils.utils import random_lower_string


async def create_random_item() -> Item:
    user = await create_random_user()
    owner_id = user.id
    assert owner_id is not None
    title = random_lower_string()
    description = random_lower_string()
    item_in = ItemCreate(title=title, description=description)
    return await crud.create_item(item_in=item_in, owner_id=owner_id)
