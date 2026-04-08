from datetime import UTC, datetime

from sqlmodel import Session, select

from app.models.v2.base import (
    AttachmentID,
    EntryID,
    ExperimentID,
    InstrumentID,
    LogbookID,
    TagID,
    UserUUID,
)
from app.models.v2.db import (
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
from app.models.v2.schemas import (
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
    return session.exec(select(Entry).where(Entry.root_id == root_id)).all()


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
    return session.exec(
        select(EntryRevision)
        .where(EntryRevision.entry_id == entry_id)
        .order_by(EntryRevision.version)
    ).all()


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
