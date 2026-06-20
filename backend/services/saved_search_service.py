"""Saved-search re-run and "new since last run" diffing.

The diff is keyed by stable `(source, source_job_id)` identity (see SavedSearch
docstring). `compute_new_ids` is a pure function over postings + a baseline set
so it can be unit-tested in isolation; `diff_run` wires it to the DB with
idempotency (a repeat call for the same run returns the cached result rather
than recomputing against an already-advanced baseline).
"""

import json
import logging
import uuid

from sqlmodel import Session, select

from backend.models.job_posting import JobPosting
from backend.models.saved_search import SavedSearch

logger = logging.getLogger(__name__)


def posting_key(source: str, source_job_id: str) -> str:
    """Stable identity for a posting across runs."""
    return f"{source}::{source_job_id}"


def compute_new_ids(postings: list[JobPosting], baseline_keys: set[str]) -> list[uuid.UUID]:
    """Return ids of *postings* whose stable key is not in *baseline_keys*.

    Pure function — no I/O. Order follows the input list.
    """
    new_ids: list[uuid.UUID] = []
    for p in postings:
        if posting_key(p.source, p.source_job_id) not in baseline_keys:
            new_ids.append(p.id)
    return new_ids


def diff_run(
    saved: SavedSearch,
    search_job_id: uuid.UUID,
    session: Session,
) -> tuple[list[uuid.UUID], bool]:
    """Diff a completed run against the saved baseline and advance the baseline.

    Idempotent per `search_job_id`: if this run was already diffed, the cached
    "new" ids are returned and nothing changes. Otherwise the current run's keys
    become the new baseline.

    Returns `(new_posting_ids, is_first_run)`. On the first ever run (empty
    baseline) the result is no-new (`[]`, True) — we only establish the baseline,
    we don't flood every posting as "new".
    """
    # Idempotent replay for the same run.
    if saved.last_diffed_job_id == search_job_id:
        cached = [uuid.UUID(s) for s in json.loads(saved.last_new_ids_json)]
        is_first_run = saved.seen_keys_json == "[]" and not cached
        return cached, is_first_run

    postings = session.exec(
        select(JobPosting).where(JobPosting.search_job_id == search_job_id)
    ).all()

    baseline: set[str] = set(json.loads(saved.seen_keys_json))
    is_first_run = len(baseline) == 0

    new_ids = [] if is_first_run else compute_new_ids(postings, baseline)

    # Advance the baseline to this run's keys; cache the computed new set.
    current_keys = sorted(posting_key(p.source, p.source_job_id) for p in postings)
    saved.seen_keys_json = json.dumps(current_keys)
    saved.last_diffed_job_id = search_job_id
    saved.last_new_ids_json = json.dumps([str(i) for i in new_ids])
    session.add(saved)
    session.commit()

    logger.info(
        "saved_search %s: diffed run %s — %d new (first_run=%s)",
        saved.id,
        search_job_id,
        len(new_ids),
        is_first_run,
    )
    return new_ids, is_first_run
