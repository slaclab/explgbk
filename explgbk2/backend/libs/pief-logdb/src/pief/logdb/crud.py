from datetime import UTC, datetime
from typing import Any, Literal

from sqlmodel import Session, col, func, select

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


def create_user(*, session: Session, user_in: UserCreate) -> User:
    user = User.model_validate(user_in)
    session.add(user)
    session.flush()
    session.refresh(user)
    return user


def get_user(*, session: Session, user_id: UserUUID) -> User | None:
    return session.get(User, user_id)


def get_user_by_username(*, session: Session, username: str) -> User | None:
    return session.exec(select(User).where(User.username == username)).first()


def create_default_user(*, session: Session, username: str) -> None:
    """Create a user with the given username if one does not already exist."""
    user = get_user_by_username(session=session, username=username)
    if not user:
        user_in = UserCreate(username=username)
        create_user(session=session, user_in=user_in)


def list_users(
    *, session: Session, skip: int = 0, limit: int = 100
) -> tuple[list[User], int]:
    count = session.exec(select(func.count()).select_from(User)).one()
    users = session.exec(select(User).offset(skip).limit(limit)).all()
    return list(users), count


def delete_user(*, session: Session, user: User) -> None:
    session.delete(user)
    session.flush()


def update_user(*, session: Session, user: User, user_update: UserUpdate) -> User:
    update_data = user_update.model_dump(exclude_unset=True)
    user.sqlmodel_update(update_data)
    session.add(user)
    session.flush()
    session.refresh(user)
    return user


def create_entry(*, session: Session, entry_in: EntryCreate) -> Entry:
    entry_data = entry_in.model_dump(exclude={"logbook_ids", "tag_ids"})
    entry = Entry.model_validate(entry_data)
    session.add(entry)
    session.flush()  # get entry.id before creating junction rows

    for logbook_id in entry_in.logbook_ids:
        session.add(LogbookEntry(entry_id=entry.id, logbook_id=logbook_id))

    for tag_id in entry_in.tag_ids:
        session.add(EntryTag(entry_id=entry.id, tag_id=tag_id))

    session.refresh(entry)
    return entry


def get_entry(*, session: Session, entry_id: EntryID) -> Entry | None:
    return session.get(Entry, entry_id)


def get_entry_by_legacy_id(*, session: Session, legacy_id: str) -> Entry | None:
    return session.exec(select(Entry).where(Entry.legacy_id == legacy_id)).first()


def retract_entry(*, session: Session, entry: Entry, retracted_by: UserUUID) -> Entry:
    entry.retracted_by = retracted_by
    entry.retracted_time = datetime.now(UTC)
    session.add(entry)
    session.flush()
    session.refresh(entry)
    return entry


def get_thread_replies(*, session: Session, root_id: EntryID) -> list[Entry]:
    return list(session.exec(select(Entry).where(Entry.root_id == root_id)).all())


def update_entry(*, session: Session, entry: Entry, entry_update: EntryUpdate) -> Entry:
    update_data = entry_update.model_dump(exclude_unset=True)
    entry.sqlmodel_update(update_data)
    entry.version += 1
    session.add(entry)
    session.flush()
    session.refresh(entry)
    return entry


def update_attachment(
    *, session: Session, attachment: Attachment, attachment_update: AttachmentUpdate
) -> Attachment:
    update_data = attachment_update.model_dump(exclude_unset=True)
    attachment.sqlmodel_update(update_data)
    session.add(attachment)
    session.flush()
    session.refresh(attachment)
    return attachment


def create_logbook(*, session: Session, logbook_in: LogbookCreate) -> Logbook:
    logbook = Logbook.model_validate(logbook_in)
    session.add(logbook)
    session.flush()
    session.refresh(logbook)
    return logbook


def get_logbook(*, session: Session, logbook_id: LogbookID) -> Logbook | None:
    return session.get(Logbook, logbook_id)


def create_entry_revision(
    *, session: Session, revision_in: EntryRevisionCreate
) -> EntryRevision:
    data = revision_in.model_dump()
    # Drop None revised_at so EntryRevision's default_factory fires instead.
    if data.get("revised_at") is None:
        data.pop("revised_at", None)
    revision = EntryRevision.model_validate(data)
    session.add(revision)
    session.flush()
    session.refresh(revision)
    return revision


def get_entry_revisions(*, session: Session, entry_id: EntryID) -> list[EntryRevision]:
    return list(
        session.exec(
            select(EntryRevision)
            .where(EntryRevision.entry_id == entry_id)
            .order_by(col(EntryRevision.version))
        ).all()
    )


def create_external_link(
    *, session: Session, link_in: ExternalLinkCreate
) -> ExternalLink:
    link = ExternalLink.model_validate(link_in)
    session.add(link)
    session.flush()
    session.refresh(link)
    return link


def create_experiment(
    *, session: Session, experiment_in: ExperimentCreate
) -> Experiment:
    experiment = Experiment.model_validate(experiment_in)
    session.add(experiment)
    session.flush()
    session.refresh(experiment)
    return experiment


def get_experiment(
    *, session: Session, experiment_id: ExperimentID
) -> Experiment | None:
    return session.get(Experiment, experiment_id)


def get_experiment_by_name(*, session: Session, name: str) -> Experiment | None:
    return session.exec(select(Experiment).where(Experiment.name == name)).first()


def get_experiment_by_legacy_id(
    *, session: Session, legacy_id: str
) -> Experiment | None:
    return session.exec(
        select(Experiment).where(Experiment.legacy_id == legacy_id)
    ).first()


def update_experiment(
    *, session: Session, experiment: Experiment, experiment_update: ExperimentUpdate
) -> Experiment:
    update_data = experiment_update.model_dump(exclude_unset=True)
    experiment.sqlmodel_update(update_data)
    session.add(experiment)
    session.flush()
    session.refresh(experiment)
    return experiment


ExperimentSortField = Literal["name", "start_time", "end_time", "created_at"]


def list_experiments(
    *,
    session: Session,
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
    count = session.exec(select(func.count()).select_from(query.subquery())).one()
    experiments = list(session.exec(query.offset(skip).limit(limit)).all())
    return experiments, count


def list_experiment_names(
    *,
    session: Session,
) -> list[str]:
    """Return all experiment names."""
    return list(session.exec(select(Experiment.name)).all())


def create_tag(*, session: Session, tag_in: TagCreate) -> Tag:
    tag = Tag.model_validate(tag_in)
    session.add(tag)
    session.flush()
    session.refresh(tag)
    return tag


def get_tag(*, session: Session, tag_id: TagID) -> Tag | None:
    return session.get(Tag, tag_id)


def get_tag_by_name(*, session: Session, name: str) -> Tag | None:
    return session.exec(select(Tag).where(Tag.name == name)).first()


def update_tag(*, session: Session, tag: Tag, tag_update: TagUpdate) -> Tag:
    update_data = tag_update.model_dump(exclude_unset=True)
    tag.sqlmodel_update(update_data)
    session.add(tag)
    session.flush()
    session.refresh(tag)
    return tag


def create_instrument(
    *, session: Session, instrument_in: InstrumentCreate
) -> Instrument:
    instrument = Instrument.model_validate(instrument_in)
    session.add(instrument)
    session.flush()
    session.refresh(instrument)
    return instrument


def get_instrument(
    *, session: Session, instrument_id: InstrumentID
) -> Instrument | None:
    return session.get(Instrument, instrument_id)


def list_instrument_experiment_counts(
    *,
    session: Session,
) -> list[tuple[InstrumentID | None, int]]:
    """Return each distinct instrument_id with the count of experiments under it."""
    return list(
        session.exec(
            select(Experiment.instrument_id, func.count().label("experiment_count"))
            .group_by(col(Experiment.instrument_id))
            .order_by(col(Experiment.instrument_id))
        ).all()
    )
