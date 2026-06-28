"""Tests for Phase 2 incremental-persist + progress-counter behaviour of run_search.

Covers:
- completed_adapters / total_adapters set correctly on the SearchJob row.
- Postings are persisted incrementally; each adapter's chunk is committed before
  the whole run finishes (verified with a controllable slow adapter).
- Cross-chunk dedup: overlapping (source, source_job_id) keys across two adapters
  produce only one persisted posting.
- A failing adapter does NOT abort the run; other adapters still persist and
  completed_adapters still advances for the failed one.
- relevance_score is non-null on every persisted posting.
- GET /search/{job_id}/status returns completed_adapters and total_adapters.
"""

import asyncio
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from backend.models.job_posting import JobPosting, RemoteStatus, SearchCriteria
from backend.models.search_job import SearchJob, SearchJobStatus
from backend.models.user import User
from backend.services.search_service import run_search

# ---------------------------------------------------------------------------
# Helpers: fake adapters
# ---------------------------------------------------------------------------


def _posting(source: str, job_id: str, title: str = "Software Engineer") -> JobPosting:
    """Build a minimal JobPosting (not yet added to session)."""
    return JobPosting(
        source=source,
        source_job_id=job_id,
        title=title,
        company="Acme",
        location="Remote",
        remote_status=RemoteStatus.remote,
        url=f"https://example.com/{source}/{job_id}",
        description="We need a software engineer.",
    )


class FastAdapter:
    """Returns two postings immediately."""

    source = "fast_board"

    async def search(self, criteria: SearchCriteria) -> list[JobPosting]:
        return [
            _posting("fast_board", "job-1", "Software Engineer"),
            _posting("fast_board", "job-2", "Backend Engineer"),
        ]


class SlowAdapter:
    """Waits on an asyncio.Event before returning, so we can inspect mid-run state."""

    source = "slow_board"

    def __init__(self, gate: asyncio.Event) -> None:
        self._gate = gate

    async def search(self, criteria: SearchCriteria) -> list[JobPosting]:
        await self._gate.wait()
        return [_posting("slow_board", "job-3", "Frontend Engineer")]


class OverlapAdapter:
    """Returns a posting with the same (source, source_job_id) as FastAdapter's first result."""

    source = "fast_board"  # same source as FastAdapter → same dedup key

    async def search(self, criteria: SearchCriteria) -> list[JobPosting]:
        # job-1 is already returned by FastAdapter; only job-99 is new.
        return [
            _posting("fast_board", "job-1", "Software Engineer"),  # duplicate
            _posting("fast_board", "job-99", "DevOps Engineer"),  # unique
        ]


class FailingAdapter:
    """Always raises, simulating a board that is down."""

    source = "failing_board"

    async def search(self, criteria: SearchCriteria) -> list[JobPosting]:
        raise RuntimeError("board is down")


# ---------------------------------------------------------------------------
# Fixture: a queued SearchJob with its own in-memory DB session
# ---------------------------------------------------------------------------


@pytest.fixture()
def search_job(session: Session, user: User) -> SearchJob:
    """Create a queued SearchJob in the test DB and return it."""
    job = SearchJob(criteria_json='{"query":"software engineer"}', user_id=user.id)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@pytest.fixture()
def criteria() -> SearchCriteria:
    return SearchCriteria(query="software engineer")


# ---------------------------------------------------------------------------
# 1. completed_adapters advances and ends equal to total_adapters
# ---------------------------------------------------------------------------


def test_counters_end_equal_to_adapter_count(
    session: Session, search_job: SearchJob, criteria: SearchCriteria
):
    """After run_search, completed_adapters == total_adapters == len(fake adapters)."""
    fake_adapters = [FastAdapter(), FastAdapter.__new__(FastAdapter)]
    fake_adapters[1].source = "second_board"

    # Give the second adapter its own unique postings.
    async def _second_search(self_inner, c):  # noqa: ANN001, ANN202
        return [_posting("second_board", "job-s1")]

    import types

    fake_adapters[1].search = types.MethodType(_second_search, fake_adapters[1])

    with patch("backend.services.search_service.get_all_adapters", return_value=fake_adapters):
        asyncio.run(run_search(search_job.id, criteria, session))

    session.refresh(search_job)
    assert search_job.total_adapters == 2
    assert search_job.completed_adapters == 2
    assert search_job.status == SearchJobStatus.complete


# ---------------------------------------------------------------------------
# 2. Incremental persist: postings visible before slow adapter completes
# ---------------------------------------------------------------------------


def test_incremental_persist_fast_before_slow(
    session: Session, search_job: SearchJob, criteria: SearchCriteria
):
    """FastAdapter's postings are committed before SlowAdapter's gate is released.

    We use a real asyncio event.  The slow adapter blocks until we manually
    release it.  We check the DB state while it is still blocked, then release.
    """
    gate = asyncio.Event()
    fast = FastAdapter()
    slow = SlowAdapter(gate)

    # We run run_search in a background thread so we can interact with the event
    # loop from the test thread.

    results: dict = {}

    async def _run_and_capture() -> None:
        task = asyncio.create_task(run_search(search_job.id, criteria, session))

        # Yield control briefly so the fast adapter can complete and commit.
        for _ in range(50):
            await asyncio.sleep(0.01)
            # Check if fast_board postings have landed already.
            committed = session.exec(
                select(JobPosting).where(JobPosting.search_job_id == search_job.id)
            ).all()
            if len(committed) >= 2:  # noqa: PLR2004
                break

        results["mid_run_count"] = len(
            session.exec(select(JobPosting).where(JobPosting.search_job_id == search_job.id)).all()
        )
        session.refresh(search_job)
        results["mid_run_completed"] = search_job.completed_adapters
        results["mid_run_status"] = search_job.status

        # Release the slow adapter.
        gate.set()
        await task

        results["final_count"] = len(
            session.exec(select(JobPosting).where(JobPosting.search_job_id == search_job.id)).all()
        )

    with patch("backend.services.search_service.get_all_adapters", return_value=[fast, slow]):
        asyncio.run(_run_and_capture())

    # Fast adapter's postings were visible before slow adapter finished.
    assert results["mid_run_count"] >= 2, (  # noqa: PLR2004
        "FastAdapter postings should be persisted before SlowAdapter gate is released"
    )
    # At least the fast adapter completed while the slow one was still waiting.
    assert results["mid_run_completed"] >= 1
    assert results["mid_run_status"] == SearchJobStatus.running

    # After both adapters finish, all 3 postings are present and run is complete.
    assert results["final_count"] == 3  # noqa: PLR2004


# ---------------------------------------------------------------------------
# 3. Cross-chunk dedup: overlapping (source, source_job_id) → only one row
# ---------------------------------------------------------------------------


def test_cross_chunk_dedup(session: Session, search_job: SearchJob, criteria: SearchCriteria):
    """Two adapters sharing a (source, source_job_id) produce only one DB row."""
    fast = FastAdapter()  # fast_board: job-1, job-2
    overlap = OverlapAdapter()  # fast_board: job-1 (dup), job-99 (new)

    with patch("backend.services.search_service.get_all_adapters", return_value=[fast, overlap]):
        asyncio.run(run_search(search_job.id, criteria, session))

    postings = session.exec(
        select(JobPosting).where(JobPosting.search_job_id == search_job.id)
    ).all()

    # Expect: job-1, job-2 (from fast), job-99 (from overlap) = 3 unique rows.
    assert len(postings) == 3  # noqa: PLR2004

    keys = {(p.source, p.source_job_id) for p in postings}
    assert ("fast_board", "job-1") in keys
    assert ("fast_board", "job-2") in keys
    assert ("fast_board", "job-99") in keys

    # Total results counter matches persisted rows.
    session.refresh(search_job)
    assert search_job.total_results == 3  # noqa: PLR2004


# ---------------------------------------------------------------------------
# 4. Failing adapter does not abort the run
# ---------------------------------------------------------------------------


def test_failing_adapter_does_not_abort(
    session: Session, search_job: SearchJob, criteria: SearchCriteria
):
    """A raising adapter is counted as completed and others still persist."""
    fast = FastAdapter()
    failing = FailingAdapter()

    with patch("backend.services.search_service.get_all_adapters", return_value=[fast, failing]):
        asyncio.run(run_search(search_job.id, criteria, session))

    session.refresh(search_job)

    # Both adapters are counted (one succeeded, one failed).
    assert search_job.completed_adapters == 2  # noqa: PLR2004
    assert search_job.total_adapters == 2  # noqa: PLR2004

    # Final status is complete, not failed.
    assert search_job.status == SearchJobStatus.complete

    # FastAdapter's postings are still persisted.
    postings = session.exec(
        select(JobPosting).where(JobPosting.search_job_id == search_job.id)
    ).all()
    assert len(postings) == 2  # noqa: PLR2004
    sources = {p.source for p in postings}
    assert "fast_board" in sources
    assert "failing_board" not in sources


def test_all_adapters_failing_still_completes(
    session: Session, search_job: SearchJob, criteria: SearchCriteria
):
    """When every adapter raises the run completes (not failed) with zero results."""
    failing1 = FailingAdapter()

    class FailingAdapter2:
        source = "also_failing"

        async def search(self, c: SearchCriteria) -> list[JobPosting]:
            raise ValueError("another board down")

    failing2 = FailingAdapter2()

    with patch(
        "backend.services.search_service.get_all_adapters", return_value=[failing1, failing2]
    ):
        asyncio.run(run_search(search_job.id, criteria, session))

    session.refresh(search_job)
    assert search_job.status == SearchJobStatus.complete
    assert search_job.completed_adapters == 2  # noqa: PLR2004
    assert search_job.total_results == 0


# ---------------------------------------------------------------------------
# 5. Relevance score is applied per chunk on insert
# ---------------------------------------------------------------------------


def test_relevance_score_set_on_all_postings(
    session: Session, search_job: SearchJob, criteria: SearchCriteria
):
    """Every persisted posting has a non-null relevance_score after run_search."""
    with patch("backend.services.search_service.get_all_adapters", return_value=[FastAdapter()]):
        asyncio.run(run_search(search_job.id, criteria, session))

    postings = session.exec(
        select(JobPosting).where(JobPosting.search_job_id == search_job.id)
    ).all()
    assert len(postings) > 0
    assert all(p.relevance_score is not None for p in postings), (
        "Every posting should receive a relevance_score on insert"
    )


def test_relevance_score_is_integer_in_range(
    session: Session, search_job: SearchJob, criteria: SearchCriteria
):
    """relevance_score values are integers in [0, 100]."""
    with patch("backend.services.search_service.get_all_adapters", return_value=[FastAdapter()]):
        asyncio.run(run_search(search_job.id, criteria, session))

    postings = session.exec(
        select(JobPosting).where(JobPosting.search_job_id == search_job.id)
    ).all()
    for p in postings:
        assert isinstance(p.relevance_score, int)
        assert 0 <= p.relevance_score <= 100  # noqa: PLR2004


# ---------------------------------------------------------------------------
# 6. Status endpoint returns completed_adapters and total_adapters
# ---------------------------------------------------------------------------


def test_status_endpoint_includes_progress_fields(client: TestClient):
    """GET /search/{job_id}/status returns completed_adapters and total_adapters."""
    with patch("backend.routers.search.start_search_task"):
        create_resp = client.post("/search", json={"query": "data engineer"})
    assert create_resp.status_code == 200
    job_id = create_resp.json()["job_id"]

    status_resp = client.get(f"/search/{job_id}/status")
    assert status_resp.status_code == 200
    data = status_resp.json()

    assert "completed_adapters" in data, "status response must include completed_adapters"
    assert "total_adapters" in data, "status response must include total_adapters"
    assert isinstance(data["completed_adapters"], int)
    assert isinstance(data["total_adapters"], int)


def test_status_endpoint_correct_values_after_run(client: TestClient, session: Session, user: User):
    """completed_adapters == total_adapters == adapter count after a completed run."""
    fast = FastAdapter()
    adapter_list = [fast]

    # Create a search job directly so we can run the service synchronously.
    job = SearchJob(criteria_json='{"query":"software engineer"}', user_id=user.id)
    session.add(job)
    session.commit()
    session.refresh(job)

    criteria = SearchCriteria(query="software engineer")

    with patch("backend.services.search_service.get_all_adapters", return_value=adapter_list):
        asyncio.run(run_search(job.id, criteria, session))

    # Use the client to inspect the status endpoint.
    # The client fixture uses the same session override so the committed rows are visible.
    status_resp = client.get(f"/search/{job.id}/status")
    assert status_resp.status_code == 200
    data = status_resp.json()

    assert data["status"] == "complete"
    assert data["total_adapters"] == 1
    assert data["completed_adapters"] == 1
    assert data["total_results"] == 2  # FastAdapter returns 2 postings


def test_status_endpoint_progress_with_failing_adapter(
    client: TestClient, session: Session, user: User
):
    """completed_adapters counts both succeeded and failed adapters."""
    fast = FastAdapter()
    failing = FailingAdapter()
    adapter_list = [fast, failing]

    job = SearchJob(criteria_json='{"query":"software engineer"}', user_id=user.id)
    session.add(job)
    session.commit()
    session.refresh(job)

    criteria = SearchCriteria(query="software engineer")

    with patch("backend.services.search_service.get_all_adapters", return_value=adapter_list):
        asyncio.run(run_search(job.id, criteria, session))

    status_resp = client.get(f"/search/{job.id}/status")
    assert status_resp.status_code == 200
    data = status_resp.json()

    assert data["status"] == "complete"
    assert data["total_adapters"] == 2  # noqa: PLR2004
    assert data["completed_adapters"] == 2  # noqa: PLR2004
    assert data["total_results"] == 2  # only fast_board's 2 postings persisted


# ---------------------------------------------------------------------------
# 7. Single adapter: simplest happy path
# ---------------------------------------------------------------------------


def test_single_adapter_happy_path(
    session: Session, search_job: SearchJob, criteria: SearchCriteria
):
    """One adapter, no complications: verify final state is fully correct."""
    with patch("backend.services.search_service.get_all_adapters", return_value=[FastAdapter()]):
        asyncio.run(run_search(search_job.id, criteria, session))

    session.refresh(search_job)
    assert search_job.status == SearchJobStatus.complete
    assert search_job.total_adapters == 1
    assert search_job.completed_adapters == 1
    assert search_job.total_results == 2  # noqa: PLR2004
    assert search_job.completed_at is not None

    postings = session.exec(
        select(JobPosting).where(JobPosting.search_job_id == search_job.id)
    ).all()
    assert len(postings) == 2  # noqa: PLR2004
    for p in postings:
        assert p.search_job_id == search_job.id


# ---------------------------------------------------------------------------
# 8. Zero adapters: edge case — no crash, run completes immediately
# ---------------------------------------------------------------------------


def test_zero_adapters_completes_cleanly(
    session: Session, search_job: SearchJob, criteria: SearchCriteria
):
    """With no adapters, run_search finishes without error, total_adapters is 0."""
    with patch("backend.services.search_service.get_all_adapters", return_value=[]):
        asyncio.run(run_search(search_job.id, criteria, session))

    session.refresh(search_job)
    assert search_job.status == SearchJobStatus.complete
    assert search_job.total_adapters == 0
    assert search_job.completed_adapters == 0
    assert search_job.total_results == 0


# ---------------------------------------------------------------------------
# 9. search_job_id not found: run_search returns silently without crashing
# ---------------------------------------------------------------------------


def test_missing_search_job_id_returns_silently(session: Session, criteria: SearchCriteria):
    """run_search with an unknown ID logs an error and returns without crashing."""
    non_existent_id = uuid.uuid4()
    # Should not raise.
    asyncio.run(run_search(non_existent_id, criteria, session))
