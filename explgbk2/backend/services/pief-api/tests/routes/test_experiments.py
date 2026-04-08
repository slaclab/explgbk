"""Tests for GET /api/v1/experiments/ routes."""

import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlmodel import Session

from pief.api.core.config import settings
from pief.logdb import crud
from pief.logdb.schemas import ExperimentCreate, InstrumentCreate

API = settings.API_V1_STR


def _make_experiment(session: Session, **kwargs):
    defaults = {
        "name": f"exp-{uuid.uuid4()}",
        "start_time": datetime.now(UTC),
    }
    exp = crud.create_experiment(
        session=session,
        experiment_in=ExperimentCreate(**{**defaults, **kwargs}),
    )
    session.commit()
    session.refresh(exp)
    return exp.id, exp.name, exp.instrument_id


def test_read_experiments(client: TestClient, postgres_engine: Engine) -> None:
    with Session(postgres_engine) as session:
        _, exp_name, _ = _make_experiment(session)

    response = client.get(f"{API}/experiments/")
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert "count" in body
    names = [e["name"] for e in body["data"]]
    assert exp_name in names


def test_read_experiments_sorted(client: TestClient, postgres_engine: Engine) -> None:
    with Session(postgres_engine) as session:
        _make_experiment(session, name=f"aaa-{uuid.uuid4()}")
        _make_experiment(session, name=f"zzz-{uuid.uuid4()}")

    response = client.get(
        f"{API}/experiments/", params={"sort_by": "name", "sort_desc": False}
    )
    assert response.status_code == 200
    names = [e["name"] for e in response.json()["data"]]
    assert names == sorted(names)


def test_read_experiments_filter_by_instrument(
    client: TestClient, postgres_engine: Engine
) -> None:
    with Session(postgres_engine) as session:
        instrument = crud.create_instrument(
            session=session, instrument_in=InstrumentCreate()
        )
        session.flush()
        instrument_id = instrument.id
        _, exp_with_name, _ = _make_experiment(session, instrument_id=instrument_id)
        _make_experiment(session)  # no instrument

    response = client.get(
        f"{API}/experiments/", params={"instrument_id": str(instrument_id)}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["data"][0]["name"] == exp_with_name


def test_read_experiment_names(client: TestClient, postgres_engine: Engine) -> None:
    with Session(postgres_engine) as session:
        _, exp_name, _ = _make_experiment(session)

    response = client.get(f"{API}/experiments/names")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert exp_name in response.json()


def test_read_experiment_by_id(client: TestClient, postgres_engine: Engine) -> None:
    with Session(postgres_engine) as session:
        exp_id, exp_name, _ = _make_experiment(session)

    response = client.get(f"{API}/experiments/{exp_id}")
    assert response.status_code == 200
    assert response.json()["name"] == exp_name


def test_read_experiment_by_id_not_found(client: TestClient) -> None:
    response = client.get(f"{API}/experiments/{uuid.uuid4()}")
    assert response.status_code == 404
