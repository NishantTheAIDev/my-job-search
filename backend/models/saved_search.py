import uuid
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class SavedSearch(SQLModel, table=True):
    """A named, persisted search the user can re-run on demand.

    Re-running spawns an ordinary SearchJob from `criteria_json`, so all of the
    normal search behaviour (relevance scoring, incremental streaming) applies.

    "New since last run" diffing is keyed by STABLE identity: `seen_keys_json`
    holds the `"source::source_job_id"` keys that made up the baseline (the last
    run that was viewed). Posting UUIDs change every run, so the baseline can't
    be keyed by them — but the diff endpoint hands back the *current* run's
    `JobPosting.id`s (which the frontend already has) for the rows whose stable
    key isn't in the baseline.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    name: str
    criteria_json: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Most recent re-run.
    last_run_at: datetime | None = None
    last_search_job_id: uuid.UUID | None = None

    # Diff baseline: JSON list of "source::source_job_id" keys seen as of the last
    # run that was diffed/viewed. Empty on a never-run saved search.
    seen_keys_json: str = "[]"

    # Idempotency for the diff endpoint: the SearchJob whose diff is currently
    # cached, plus the cached "new" posting ids (JSON list of UUID strings) so
    # repeat calls / page refreshes return the same set instead of recomputing
    # to empty after the baseline has advanced.
    last_diffed_job_id: uuid.UUID | None = None
    last_new_ids_json: str = "[]"
