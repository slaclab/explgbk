from app.models.user import User, UserCreate, UserUpdate


async def create_user(*, user_create: UserCreate) -> User:
    db_obj = User(**user_create.model_dump())
    await db_obj.insert()
    return db_obj


async def update_user(*, db_user: User, user_in: UserUpdate) -> User:
    user_data = user_in.model_dump(exclude_unset=True)
    await db_user.set(user_data)
    return db_user


async def get_user_by_email(*, email: str) -> User | None:
    return await User.find_one(User.email == email)
