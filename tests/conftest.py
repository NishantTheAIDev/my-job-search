import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from backend.app import app
from backend.database import get_session
from backend.limiter import limiter


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


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        yield session

    app.dependency_overrides[get_session] = get_session_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
