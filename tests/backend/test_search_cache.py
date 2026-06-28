"""Tests for the same-day search result cache (Task 3).

Invariants verified:
1. compute_criteria_fingerprint is deterministic and stable.
2. Different criteria produce different fingerprints.
3. POST /search with no same-day match queues a new job (cached=False).
4. POST /search with a same-day completed match returns the cached job (cached=True).
5. POST /search?force=true always creates a new job even when a cache hit exists.
6. A completed SearchJob from a prior calendar day is NOT treated as a cache hit.
7. A failed or running SearchJob is NOT treated as a cache hit.
8. Cache is scoped to the authenticated user — other user's completed jobs are invisible.
9. SearchJob rows created via POST /search carry a non-empty criteria_fingerprint.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.models.job_posting import SearchCriteria
from backend.models.search_job import SearchJob, SearchJobStatus
from backend.models.user import User
from backend.services.search_service import compute_criteria_fingerprint

# ---------------------------------------------------------------------------
# Unit tests for compute_criteria_fingerprint
# ---------------------------------------------------------------------------


def test_fingerprint_is_deterministic():
    c = SearchCriteria(query="python developer", location="London", remote_only=False, page=1)
    assert compute_criteria_fingerprint(c) == compute_criteria_fingerprint(c)


def test_fingerprint_normalises_query_case_and_whitespace():
    c1 = SearchCriteria(query="  Python Developer  ", page=1)
    c2 = SearchCriteria(query="python developer", page=1)
    assert compute_criteria_fingerprint(c1) == compute_criteria_fingerprint(c2)


def test_fingerprint_normalises_location_case_and_whitespace():
    c1 = SearchCriteria(query="engineer", location="  New York  ", page=1)
    c2 = SearchCriteria(query="engineer", location="new york", page=1)
    assert compute_criteria_fingerprint(c1) == compute_criteria_fingerprint(c2)


def test_fingerprint_differs_for_different_query():
    c1 = SearchCriteria(query="python", page=1)
    c2 = SearchCriteria(query="java", page=1)
    assert compute_criteria_fingerprint(c1) != compute_criteria_fingerprint(c2)


def test_fingerprint_differs_for_different_page():
    c1 = SearchCriteria(query="python", page=1)
    c2 = SearchCriteria(query="python", page=2)
    assert compute_criteria_fingerprint(c1) != compute_criteria_fingerprint(c2)


def test_fingerprint_differs_for_remote_only_flag():
    c1 = SearchCriteria(query="engineer", remote_only=True, page=1)
    c2 = SearchCriteria(query="engineer", remote_only=False, page=1)
    assert compute_criteria_fingerprint(c1) != compute_criteria_fingerprint(c2)


def test_fingerprint_is_hex_string():
    c = SearchCriteria(query="test", page=1)
    fp = compute_criteria_fingerprint(c)
    assert isinstance(fp, str)
    assert len(fp) == 64  # SHA-256 hex digest
    int(fp, 16)  # must be valid hex


# ---------------------------------------------------------------------------
# Helpers for HTTP route tests
# ---------------------------------------------------------------------------


def _seed_completed_search(
    session: Session,
    user_id: uuid.UUID,
    fingerprint: str,
    created_at: datetime,
    status: SearchJobStatus = SearchJobStatus.complete,
) -> SearchJob:
    job = SearchJob(
        user_id=user_id,
        criteria_json='{"query":"python","page":1}',
        criteria_fingerprint=fingerprint,
        status=status,
        created_at=created_at,
        completed_at=created_at,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


# ---------------------------------------------------------------------------
# HTTP route tests
# ---------------------------------------------------------------------------


CRITERIA = {"query": "python developer", "page": 1}


def test_new_search_queues_job_and_returns_cached_false(client: TestClient):
    with patch("backend.routers.search.start_search_task"):
        resp = client.post("/search", json=CRITERIA)
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["cached"] is False
    assert data["status"] == "queued"


def test_new_search_stamps_fingerprint_on_job(client: TestClient, session: Session, user: User):
    with patch("backend.routers.search.start_search_task"):
        resp = client.post("/search", json=CRITERIA)
    job_id = resp.json()["job_id"]
    job = session.get(SearchJob, uuid.UUID(job_id))
    assert job is not None
    assert len(job.criteria_fingerprint) == 64


def test_cache_hit_returns_existing_job_id(client: TestClient, session: Session, user: User):
    criteria = SearchCriteria(**CRITERIA)
    fp = compute_criteria_fingerprint(criteria)
    existing = _seed_completed_search(session, user.id, fp, datetime.now(UTC))

    with patch("backend.routers.search.start_search_task") as mock_task:
        resp = client.post("/search", json=CRITERIA)

    assert resp.status_code == 200
    data = resp.json()
    assert data["cached"] is True
    assert data["job_id"] == str(existing.id)
    assert data["status"] == "complete"
    mock_task.assert_not_called()


def test_force_true_bypasses_cache(client: TestClient, session: Session, user: User):
    criteria = SearchCriteria(**CRITERIA)
    fp = compute_criteria_fingerprint(criteria)
    existing = _seed_completed_search(session, user.id, fp, datetime.now(UTC))

    with patch("backend.routers.search.start_search_task"):
        resp = client.post("/search?force=true", json=CRITERIA)

    assert resp.status_code == 200
    data = resp.json()
    assert data["cached"] is False
    # A brand-new job was created, not the seeded one.
    assert data["job_id"] != str(existing.id)
    assert data["status"] == "queued"


def test_cache_miss_for_yesterday_job(client: TestClient, session: Session, user: User):
    """A completed job created yesterday must NOT be served as a cache hit."""
    criteria = SearchCriteria(**CRITERIA)
    fp = compute_criteria_fingerprint(criteria)
    yesterday = datetime.now(UTC) - timedelta(days=1)
    _seed_completed_search(session, user.id, fp, yesterday)

    with patch("backend.routers.search.start_search_task"):
        resp = client.post("/search", json=CRITERIA)

    assert resp.status_code == 200
    data = resp.json()
    assert data["cached"] is False
    assert data["status"] == "queued"


def test_cache_miss_for_failed_job(client: TestClient, session: Session, user: User):
    """A failed SearchJob (even from today) must NOT be served as a cache hit."""
    criteria = SearchCriteria(**CRITERIA)
    fp = compute_criteria_fingerprint(criteria)
    _seed_completed_search(session, user.id, fp, datetime.now(UTC), status=SearchJobStatus.failed)

    with patch("backend.routers.search.start_search_task"):
        resp = client.post("/search", json=CRITERIA)

    assert resp.status_code == 200
    assert resp.json()["cached"] is False


def test_cache_miss_for_running_job(client: TestClient, session: Session, user: User):
    """A running SearchJob must NOT be served as a cache hit."""
    criteria = SearchCriteria(**CRITERIA)
    fp = compute_criteria_fingerprint(criteria)
    _seed_completed_search(session, user.id, fp, datetime.now(UTC), status=SearchJobStatus.running)

    with patch("backend.routers.search.start_search_task"):
        resp = client.post("/search", json=CRITERIA)

    assert resp.status_code == 200
    assert resp.json()["cached"] is False


def test_cache_is_user_scoped(session: Session, user: User, other_user: User, make_client):
    """A cache hit for user B must not be served to user A."""
    criteria = SearchCriteria(**CRITERIA)
    fp = compute_criteria_fingerprint(criteria)
    # Seed a completed job for other_user only.
    _seed_completed_search(session, other_user.id, fp, datetime.now(UTC))

    client_a = make_client(user)
    with patch("backend.routers.search.start_search_task"):
        resp = client_a.post("/search", json=CRITERIA)

    assert resp.status_code == 200
    data = resp.json()
    assert data["cached"] is False


def test_cache_miss_for_different_criteria(client: TestClient, session: Session, user: User):
    """Criteria that differ on any field must not match a cached result."""
    criteria_a = SearchCriteria(query="python", page=1)
    fp_a = compute_criteria_fingerprint(criteria_a)
    _seed_completed_search(session, user.id, fp_a, datetime.now(UTC))

    with patch("backend.routers.search.start_search_task"):
        resp = client.post("/search", json={"query": "java", "page": 1})

    assert resp.status_code == 200
    assert resp.json()["cached"] is False
