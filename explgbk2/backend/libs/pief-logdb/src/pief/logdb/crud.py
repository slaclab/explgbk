from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, func, select

from pief.logdb.base import (
    EntryID,
    ExperimentID,
    InstrumentID,
    LogbookID,
    TagID,
    UserUUID,
)
from pief.logdb.tables import (
    Attachment,
    Entry,
    EntryRevision,
    EntryTag,
    Experiment,
    ExternalLink,
    Instrument,
    Logbook,
    LogbookEntry,
    Tag,
    User,
)
from pief.logdb.schemas import (
    AttachmentUpdate,
    EntryCreate,
    EntryRevisionCreate,
    EntryUpdate,
    ExperimentCreate,
    ExperimentUpdate,
    ExternalLinkCreate,
    InstrumentCreate,
    LogbookCreate,
    TagCreate,
    TagUpdate,
    UserCreate,
    UserUpdate,
)


async def create_user(*, session: AsyncSession, user_in: UserCreate) -> User:
    user = User.model_validate(user_in)
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def get_user(*, session: AsyncSession, user_id: UserUUID) -> User | None:
    return await session.get(User, user_id)


async def get_user_by_username(*, session: AsyncSession, username: str) -> User | None:
    result = await session.execute(select(User).where(User.username == username))
    return result.scalars().first()


async def list_users(
    *, session: AsyncSession, skip: int = 0, limit: int = 100
) -> tuple[list[User], int]:
    count_result = await session.execute(select(func.count()).select_from(User))
    count = count_result.scalar_one()
    users_result = await session.execute(select(User).offset(skip).limit(limit))
    return list(users_result.scalars().all()), count


async def delete_user(*, session: AsyncSession, user: User) -> None:
    await session.delete(user)
    await session.flush()


async def update_user(
    *, session: AsyncSession, user: User, user_update: UserUpdate
) -> User:
    update_data = user_update.model_dump(exclude_unset=True)
    user.sqlmodel_update(update_data)
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def create_entry(*, session: AsyncSession, entry_in: EntryCreate) -> Entry:
    entry_data = entry_in.model_dump(exclude={"logbook_ids", "tag_ids"})
    entry = Entry.model_validate(entry_data)
    session.add(entry)
    await session.flush()  # get entry.id before creating junction rows

    for logbook_id in entry_in.logbook_ids:
        session.add(LogbookEntry(entry_id=entry.id, logbook_id=logbook_id))

    for tag_id in entry_in.tag_ids:
        session.add(EntryTag(entry_id=entry.id, tag_id=tag_id))

    await session.refresh(entry)
    return entry


async def get_entry(*, session: AsyncSession, entry_id: EntryID) -> Entry | None:
    return await session.get(Entry, entry_id)


async def get_entry_by_legacy_id(
    *, session: AsyncSession, legacy_id: str
) -> Entry | None:
    result = await session.execute(select(Entry).where(Entry.legacy_id == legacy_id))
    return result.scalars().first()


async def retract_entry(
    *, session: AsyncSession, entry: Entry, retracted_by: UserUUID
) -> Entry:
    entry.retracted_by = retracted_by
    entry.retracted_time = datetime.now(UTC)
    session.add(entry)
    await session.flush()
    await session.refresh(entry)
    return entry


async def get_thread_replies(*, session: AsyncSession, root_id: EntryID) -> list[Entry]:
    result = await session.execute(select(Entry).where(Entry.root_id == root_id))
    return list(result.scalars().all())


async def update_entry(
    *, session: AsyncSession, entry: Entry, entry_update: EntryUpdate
) -> Entry:
    update_data = entry_update.model_dump(exclude_unset=True)
    entry.sqlmodel_update(update_data)
    entry.version += 1
    session.add(entry)
    await session.flush()
    await session.refresh(entry)
    return entry


async def update_attachment(
    *,
    session: AsyncSession,
    attachment: Attachment,
    attachment_update: AttachmentUpdate,
) -> Attachment:
    update_data = attachment_update.model_dump(exclude_unset=True)
    attachment.sqlmodel_update(update_data)
    session.add(attachment)
    await session.flush()
    await session.refresh(attachment)
    return attachment


async def create_logbook(
    *, session: AsyncSession, logbook_in: LogbookCreate
) -> Logbook:
    logbook = Logbook.model_validate(logbook_in)
    session.add(logbook)
    await session.flush()
    await session.refresh(logbook)
    return logbook


async def get_logbook(
    *, session: AsyncSession, logbook_id: LogbookID
) -> Logbook | None:
    return await session.get(Logbook, logbook_id)


async def create_entry_revision(
    *, session: AsyncSession, revision_in: EntryRevisionCreate
) -> EntryRevision:
    data = revision_in.model_dump()
    # Drop None revised_at so EntryRevision's default_factory fires instead.
    if data.get("revised_at") is None:
        data.pop("revised_at", None)
    revision = EntryRevision.model_validate(data)
    session.add(revision)
    await session.flush()
    await session.refresh(revision)
    return revision


async def get_entry_revisions(
    *, session: AsyncSession, entry_id: EntryID
) -> list[EntryRevision]:
    result = await session.execute(
        select(EntryRevision)
        .where(EntryRevision.entry_id == entry_id)
        .order_by(col(EntryRevision.version))
    )
    return list(result.scalars().all())


async def create_external_link(
    *, session: AsyncSession, link_in: ExternalLinkCreate
) -> ExternalLink:
    link = ExternalLink.model_validate(link_in)
    session.add(link)
    await session.flush()
    await session.refresh(link)
    return link


async def create_experiment(
    *, session: AsyncSession, experiment_in: ExperimentCreate
) -> Experiment:
    experiment = Experiment.model_validate(experiment_in)
    session.add(experiment)
    await session.flush()
    await session.refresh(experiment)
    return experiment


async def get_experiment(
    *, session: AsyncSession, experiment_id: ExperimentID
) -> Experiment | None:
    return await session.get(Experiment, experiment_id)


async def get_experiment_by_name(
    *, session: AsyncSession, name: str
) -> Experiment | None:
    result = await session.execute(select(Experiment).where(Experiment.name == name))
    return result.scalars().first()


async def get_experiment_by_legacy_id(
    *, session: AsyncSession, legacy_id: str
) -> Experiment | None:
    result = await session.execute(
        select(Experiment).where(Experiment.legacy_id == legacy_id)
    )
    return result.scalars().first()


async def update_experiment(
    *,
    session: AsyncSession,
    experiment: Experiment,
    experiment_update: ExperimentUpdate,
) -> Experiment:
    update_data = experiment_update.model_dump(exclude_unset=True)
    experiment.sqlmodel_update(update_data)
    session.add(experiment)
    await session.flush()
    await session.refresh(experiment)
    return experiment


ExperimentSortField = Literal["name", "start_time", "end_time", "created_at"]


async def list_experiments(
    *,
    session: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    sort_by: ExperimentSortField = "name",
    sort_desc: bool = False,
    instrument_id: InstrumentID | None = None,
) -> tuple[list[Experiment], int]:
    """Return a paginated, sorted list of experiments and total count."""
    query = select(Experiment)
    if instrument_id is not None:
        query = query.where(Experiment.instrument_id == instrument_id)
    _sort_cols: dict[str, Any] = {
        "name": col(Experiment.name),
        "start_time": col(Experiment.start_time),
        "end_time": col(Experiment.end_time),
        "created_at": col(Experiment.created_at),
    }
    sort_col = _sort_cols[sort_by]
    query = query.order_by(sort_col.desc() if sort_desc else sort_col)
    count_result = await session.execute(
        select(func.count()).select_from(query.subquery())
    )
    count = count_result.scalar_one()
    experiments_result = await session.execute(query.offset(skip).limit(limit))
    return list(experiments_result.scalars().all()), count


async def list_experiment_names(*, session: AsyncSession) -> list[str]:
    """Return all experiment names."""
    result = await session.execute(select(Experiment.name))
    return list(result.scalars().all())


async def create_tag(*, session: AsyncSession, tag_in: TagCreate) -> Tag:
    tag = Tag.model_validate(tag_in)
    session.add(tag)
    await session.flush()
    await session.refresh(tag)
    return tag


async def get_tag(*, session: AsyncSession, tag_id: TagID) -> Tag | None:
    return await session.get(Tag, tag_id)


async def get_tag_by_name(*, session: AsyncSession, name: str) -> Tag | None:
    result = await session.execute(select(Tag).where(Tag.name == name))
    return result.scalars().first()


async def update_tag(*, session: AsyncSession, tag: Tag, tag_update: TagUpdate) -> Tag:
    update_data = tag_update.model_dump(exclude_unset=True)
    tag.sqlmodel_update(update_data)
    session.add(tag)
    await session.flush()
    await session.refresh(tag)
    return tag


async def create_instrument(
    *, session: AsyncSession, instrument_in: InstrumentCreate
) -> Instrument:
    instrument = Instrument.model_validate(instrument_in)
    session.add(instrument)
    await session.flush()
    await session.refresh(instrument)
    return instrument


async def get_instrument(
    *, session: AsyncSession, instrument_id: InstrumentID
) -> Instrument | None:
    return await session.get(Instrument, instrument_id)
