"""Tests for GET /api/v1/users/ routes."""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from pief.api.core.config import settings
from pief.logdb.tables import User

API = settings.API_V1_STR


def _make_user(session: Session, **kwargs) -> tuple[uuid.UUID, str]:
    defaults: dict = {"username": f"user-{uuid.uuid4()}"}
    user = User(**{**defaults, **kwargs})
    session.add(user)
    session.commit()
    session.refresh(user)
    return user.id, user.username


def test_read_users(client: TestClient, postgres_engine: Engine) -> None:
    with Session(postgres_engine) as session:
        _make_user(session)

    response = client.get(f"{API}/users/")
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert "count" in body
    assert body["count"] >= 1


def test_read_user_me(client: TestClient) -> None:
    response = client.get(f"{API}/users/me")
    assert response.status_code == 200
    assert response.json()["username"] == settings.FIRST_SUPERUSER


def test_read_user_by_id(client: TestClient, postgres_engine: Engine) -> None:
    with Session(postgres_engine) as session:
        user_id, username = _make_user(session)

    response = client.get(f"{API}/users/{user_id}")
    assert response.status_code == 200
    assert response.json()["username"] == username


def test_read_user_by_id_not_found(client: TestClient) -> None:
    response = client.get(f"{API}/users/{uuid.uuid4()}")
    assert response.status_code == 404
