"""Tests for the /auth endpoints and the get_current_user dependency.

These exercise the REAL auth path (register/login/JWT verification), unlike the
route tests which override get_current_user via the `client` fixture. So this
module builds its own unauthenticated TestClient against the test session.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.app import app
from backend.database import get_session


@pytest.fixture(name="anon_client")
def anon_client_fixture(session: Session):
    """A TestClient with NO auth override — real JWT verification applies."""

    def get_session_override():
        yield session

    app.dependency_overrides[get_session] = get_session_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _register(client: TestClient, email="alice@example.com", password="hunter2pw") -> str:
    resp = client.post("/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_register_returns_token(anon_client: TestClient):
    token = _register(anon_client)
    assert token


def test_register_duplicate_email_returns_409(anon_client: TestClient):
    _register(anon_client, email="dup@example.com")
    resp = anon_client.post(
        "/auth/register", json={"email": "dup@example.com", "password": "another1"}
    )
    assert resp.status_code == 409


def test_login_with_correct_password_returns_token(anon_client: TestClient):
    _register(anon_client, email="bob@example.com", password="correct-horse")
    resp = anon_client.post(
        "/auth/login", json={"email": "bob@example.com", "password": "correct-horse"}
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_login_with_wrong_password_returns_401(anon_client: TestClient):
    _register(anon_client, email="carol@example.com", password="right-pass")
    resp = anon_client.post(
        "/auth/login", json={"email": "carol@example.com", "password": "wrong-pass"}
    )
    assert resp.status_code == 401


def test_login_unknown_email_returns_401(anon_client: TestClient):
    resp = anon_client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "whatever1"}
    )
    assert resp.status_code == 401


def test_email_is_normalized_to_lowercase(anon_client: TestClient):
    _register(anon_client, email="Mixed@Example.com", password="pass1234")
    # Login with a different case must still match.
    resp = anon_client.post(
        "/auth/login", json={"email": "mixed@example.com", "password": "pass1234"}
    )
    assert resp.status_code == 200


def test_me_with_valid_token_returns_user(anon_client: TestClient):
    token = _register(anon_client, email="dave@example.com")
    resp = anon_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "dave@example.com"


def test_me_without_token_returns_401(anon_client: TestClient):
    assert anon_client.get("/auth/me").status_code == 401


def test_me_with_garbage_token_returns_401(anon_client: TestClient):
    resp = anon_client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401


def test_protected_route_requires_auth(anon_client: TestClient):
    """A representative protected route 401s without a token."""
    assert anon_client.get("/resume").status_code == 401
