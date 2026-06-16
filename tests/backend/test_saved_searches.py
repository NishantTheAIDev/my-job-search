"""Tests for Phase 3 — saved searches + on-demand re-run with "new" diffing.

Covers the router CRUD + run + diff endpoints and the diffing service
(stable-key baseline, idempotency, first-run no-flood, baseline advance).
"""

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.models.job_posting import JobPosting
from backend.models.saved_search import SavedSearch
from backend.models.search_job import SearchJob, SearchJobStatus
from backend.services.saved_search_service import (
    compute_new_ids,
    diff_run,
    posting_key,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_completed_run(session: Session, *keys: tuple[str, str]) -> uuid.UUID:
    """Create a complete SearchJob with one JobPosting per (source, source_job_id)."""
    job = SearchJob(
        criteria_json='{"query": "ai engineer"}',
        status=SearchJobStatus.complete,
        created_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        total_results=len(keys),
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    for source, sjid in keys:
        session.add(
            JobPosting(
                search_job_id=job.id,
                source=source,
                source_job_id=sjid,
                title="AI Engineer",
                url=f"https://example.com/{source}/{sjid}",
                description="",
            )
        )
    session.commit()
    return job.id


def _make_saved(session: Session, **kwargs) -> SavedSearch:
    saved = SavedSearch(
        name=kwargs.pop("name", "My AI search"),
        criteria_json=kwargs.pop("criteria_json", '{"query": "ai engineer"}'),
        **kwargs,
    )
    session.add(saved)
    session.commit()
    session.refresh(saved)
    return saved


# ---------------------------------------------------------------------------
# Pure diffing logic
# ---------------------------------------------------------------------------


def test_posting_key_is_stable():
    assert posting_key("adzuna", "abc") == "adzuna::abc"


def test_compute_new_ids_returns_only_unseen():
    p1 = JobPosting(source="a", source_job_id="1", title="t", url="u", description="")
    p2 = JobPosting(source="a", source_job_id="2", title="t", url="u", description="")
    baseline = {"a::1"}
    new_ids = compute_new_ids([p1, p2], baseline)
    assert new_ids == [p2.id]


def test_compute_new_ids_all_new_when_baseline_empty():
    p1 = JobPosting(source="a", source_job_id="1", title="t", url="u", description="")
    assert compute_new_ids([p1], set()) == [p1.id]


# ---------------------------------------------------------------------------
# diff_run service: first run, advance, idempotency
# ---------------------------------------------------------------------------


def test_diff_run_first_run_reports_no_new_but_sets_baseline(session: Session):
    saved = _make_saved(session)
    job_id = _make_completed_run(session, ("a", "1"), ("a", "2"))

    new_ids, is_first_run = diff_run(saved, job_id, session)

    assert is_first_run is True
    assert new_ids == []  # don't flood every posting as "new" on first run
    # Baseline now holds the current run's stable keys.
    assert set(json.loads(saved.seen_keys_json)) == {"a::1", "a::2"}
    assert saved.last_diffed_job_id == job_id


def test_diff_run_second_run_flags_only_new(session: Session):
    saved = _make_saved(session)
    first = _make_completed_run(session, ("a", "1"), ("a", "2"))
    diff_run(saved, first, session)  # establish baseline {a::1, a::2}

    second = _make_completed_run(session, ("a", "1"), ("a", "3"), ("b", "9"))
    new_ids, is_first_run = diff_run(saved, second, session)

    assert is_first_run is False
    assert len(new_ids) == 2  # a::3 and b::9 are new; a::1 was seen
    # Baseline advanced to the second run.
    assert set(json.loads(saved.seen_keys_json)) == {"a::1", "a::3", "b::9"}


def test_diff_run_is_idempotent_for_same_run(session: Session):
    saved = _make_saved(session)
    first = _make_completed_run(session, ("a", "1"))
    diff_run(saved, first, session)

    second = _make_completed_run(session, ("a", "1"), ("a", "2"))
    new_first_call, _ = diff_run(saved, second, session)
    baseline_after_first = saved.seen_keys_json

    # Repeat call for the SAME run must return the same set, not recompute to empty.
    new_second_call, _ = diff_run(saved, second, session)
    assert new_second_call == new_first_call
    assert saved.seen_keys_json == baseline_after_first


# ---------------------------------------------------------------------------
# Router CRUD
# ---------------------------------------------------------------------------


def test_create_and_list_saved_search(client: TestClient):
    resp = client.post(
        "/saved-searches",
        json={"name": "Remote AI", "criteria": {"query": "ai engineer", "remote_only": True}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Remote AI"
    assert data["criteria"]["query"] == "ai engineer"
    assert data["criteria"]["remote_only"] is True
    assert data["last_run_at"] is None

    listed = client.get("/saved-searches").json()
    assert len(listed) == 1
    assert listed[0]["id"] == data["id"]


def test_create_saved_search_rejects_blank_name(client: TestClient):
    resp = client.post(
        "/saved-searches",
        json={"name": "", "criteria": {"query": "ai engineer"}},
    )
    assert resp.status_code == 422


def test_delete_saved_search(client: TestClient):
    created = client.post(
        "/saved-searches",
        json={"name": "Temp", "criteria": {"query": "ai"}},
    ).json()
    sid = created["id"]

    assert client.delete(f"/saved-searches/{sid}").status_code == 200
    assert client.get("/saved-searches").json() == []
    assert client.delete(f"/saved-searches/{sid}").status_code == 404


# ---------------------------------------------------------------------------
# Router run + diff
# ---------------------------------------------------------------------------


def test_run_creates_search_job_from_saved_criteria(client: TestClient, session: Session):
    created = client.post(
        "/saved-searches",
        json={"name": "Run me", "criteria": {"query": "ml engineer", "remote_only": True}},
    ).json()
    sid = created["id"]

    with patch("backend.routers.saved_searches.start_search_task") as task:
        resp = client.post(f"/saved-searches/{sid}/run")
    assert resp.status_code == 200
    body = resp.json()
    assert body["saved_search_id"] == sid
    assert body["status"] == SearchJobStatus.queued.value
    task.assert_called_once()

    # A real SearchJob row exists with the saved criteria.
    job = session.get(SearchJob, uuid.UUID(body["search_job_id"]))
    assert job is not None
    assert "ml engineer" in job.criteria_json

    # last_run_at / last_search_job_id were recorded.
    saved = client.get("/saved-searches").json()[0]
    assert saved["last_run_at"] is not None
    assert saved["last_search_job_id"] == body["search_job_id"]


def test_run_missing_saved_search_returns_404(client: TestClient):
    with patch("backend.routers.saved_searches.start_search_task"):
        resp = client.post(f"/saved-searches/{uuid.uuid4()}/run")
    assert resp.status_code == 404


def test_diff_endpoint_flags_new_postings(client: TestClient, session: Session):
    saved = _make_saved(session)
    first = _make_completed_run(session, ("a", "1"))
    # First diff establishes baseline (no-new).
    r1 = client.post(f"/saved-searches/{saved.id}/diff?search_job_id={first}")
    assert r1.status_code == 200
    assert r1.json()["is_first_run"] is True
    assert r1.json()["new_count"] == 0

    second = _make_completed_run(session, ("a", "1"), ("a", "2"))
    r2 = client.post(f"/saved-searches/{saved.id}/diff?search_job_id={second}")
    assert r2.status_code == 200
    body = r2.json()
    assert body["new_count"] == 1
    assert len(body["new_posting_ids"]) == 1
    assert body["is_first_run"] is False


def test_diff_endpoint_rejects_incomplete_run(client: TestClient, session: Session):
    saved = _make_saved(session)
    job = SearchJob(
        criteria_json='{"query": "x"}',
        status=SearchJobStatus.running,
        created_at=datetime.now(UTC),
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    resp = client.post(f"/saved-searches/{saved.id}/diff?search_job_id={job.id}")
    assert resp.status_code == 409


def test_diff_endpoint_missing_search_job_returns_404(client: TestClient, session: Session):
    saved = _make_saved(session)
    resp = client.post(f"/saved-searches/{saved.id}/diff?search_job_id={uuid.uuid4()}")
    assert resp.status_code == 404
