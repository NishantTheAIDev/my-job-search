import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from backend.app import app
from backend.auth.dependencies import get_current_user
from backend.database import get_session
from backend.limiter import limiter
from backend.models.user import User


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Clear the shared slowapi limiter between tests.

    The Limiter in backend/limiter.py is a module-level singleton, so its
    request counts persist across tests. Without a reset, suites that exercise
    rate-limited endpoints (e.g. /resume/upload at 10/min, /jobs/manual at
    5/min) accumulate hits and spuriously 429 later tests.
    """
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="user")
def user_fixture(session: Session) -> User:
    """The default authenticated user (tenant A) the `client` fixture acts as."""
    u = User(email="user-a@example.com", password_hash="x")
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


@pytest.fixture(name="other_user")
def other_user_fixture(session: Session) -> User:
    """A second user (tenant B) for cross-tenant isolation tests."""
    u = User(email="user-b@example.com", password_hash="x")
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


@pytest.fixture(name="client")
def client_fixture(session: Session, user: User):
    """TestClient authenticated as the default user (tenant A).

    get_current_user is overridden so route tests don't need real JWTs; the
    auth/JWT machinery itself is covered by dedicated tests in test_auth.py.
    """

    def get_session_override():
        yield session

    app.dependency_overrides[get_session] = get_session_override
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(name="make_client")
def make_client_fixture(session: Session):
    """Factory yielding a TestClient authenticated as an explicit user.

    For cross-tenant tests: seed rows directly via `session` (stamped with one
    user's id), then drive requests as another user and assert 404.
    """

    def get_session_override():
        yield session

    def _make(acting_user: User) -> TestClient:
        app.dependency_overrides[get_session] = get_session_override
        app.dependency_overrides[get_current_user] = lambda: acting_user
        return TestClient(app)

    yield _make
    app.dependency_overrides.clear()
