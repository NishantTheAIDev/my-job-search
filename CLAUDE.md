# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

An AI-powered job search and application assistant. Searches Adzuna (+ Greenhouse/Lever company boards), scores listings against the candidate's resume via Claude, tailors the resume and drafts cover letters, then submits — but **only after explicit user approval** (a hard invariant enforced at the service layer, not just the UI).

**Stack**: Python 3.14 / FastAPI / SQLModel (SQLite) / Anthropic SDK — managed with `uv`. React 19 / TypeScript / Vite / Tailwind CSS 4 / TanStack Query / Zustand frontend.

## Commands

```bash
# Backend
uv sync --extra dev          # install all deps including dev
uv run main.py               # start FastAPI on :8000 (reload enabled)
uv run pytest                # all backend tests
uv run pytest tests/backend/test_approval_gate.py -v   # single file
uv run pytest path/to/test.py::test_name               # single test
uv add <package>             # add backend dependency
uv run ruff check .          # lint
uv run ruff check --fix .    # lint + auto-fix
uv run ruff format .         # format

# Frontend (from frontend/)
npm run dev                  # Vite dev server on :5173
npm run build                # TypeScript check + production build
npx vitest run               # run frontend tests once
npx vitest                   # watch mode
```

## Architecture

### Backend data flow

```
POST /search
  → creates SearchJob (queued)
  → FastAPI BackgroundTasks → background/tasks.py::start_search_task
  → services/search_service.py::run_search
      asyncio.gather(*[adapter.search(criteria) for adapter in get_all_adapters()],
                     return_exceptions=True)   ← one board failing doesn't abort
  → persists JobPosting rows, marks SearchJob complete

POST /jobs/{id}/prepare
  → background/tasks.py::prepare_application_task
  → services/application_service.py::prepare_application
      _parse_jd() → LLM call (jd_parser prompt)
      scoring_service.score_resume() → LLM call
      tailoring_service.tailor_resume() → LLM call + difflib diff
      drafting_service.draft_cover_letter() → LLM call
  → creates Application(status=pending)

POST /applications/{id}/approve   ← ONLY submission path
  → application_service.approve_application()
      asserts status == pending (raises InvalidStateError → 409 otherwise)
      calls submission_service.submit()  ← imported inside function body (makes call site explicit)
      writes Application(status=submitted) + AuditLog in ONE session.commit()
```

### Background task session lifecycle

**Critical**: Background tasks must create their own `Session(engine)` — never reuse the request session. FastAPI closes the request session before background tasks execute, so passing it produces silent "no active resume" failures. Pattern:

```python
def my_task(some_id: uuid.UUID) -> None:
    with Session(engine) as session:
        asyncio.run(my_async_service(some_id, session))
```

### LLM client pattern

All Claude calls go through `backend/llm/client.py::call_claude()`. Never call `anthropic.AsyncAnthropic()` elsewhere.

- System prompts are **literal strings** — never interpolated with external content
- External text (job descriptions, scraped content) goes in the **user turn only**, wrapped in named XML tags: `<job_description>`, `<resume>`, `<parsed_jd>`, `<role_title>`, `<company>`
- Every system prompt has a `SECURITY:` block instructing the model to treat tagged content as data only
- `backend/llm/sanitize.py::sanitize_jd_text()` strips control chars and truncates to 12 000 chars before any scraped text enters a prompt
- `call_claude()` logs model, token counts (including cache hits), and latency for every call

### Logging

Centralized in `backend/logging_config.py`. Call `configure_logging(level)` once at startup (done in `backend/app.py` on import). All modules use the standard `logging.getLogger(__name__)` pattern.

- Format: `YYYY-MM-DD HH:MM:SS | LEVEL | request_id | module | message`
- `request_id` is a `ContextVar` set per-request by `RequestLoggingMiddleware`; background tasks show `-`
- `RequestLoggingMiddleware` logs every HTTP request with method, path, status, duration, and echoes the ID in `X-Request-ID` response header
- Third-party libraries (`httpx`, `anthropic`, `uvicorn.access`) are silenced to WARNING
- `LOG_LEVEL` env var controls root level (default `INFO`)

### Rate limiting

`backend/limiter.py` holds the shared `slowapi.Limiter` instance. Import from there — never create a second `Limiter`. Applied to: `POST /resume/upload` (10/min), `POST /search` (5/min), `POST /applications/{id}/approve` (20/min). Route handlers that use it need `request: Request` as their first parameter.

### Adapter pattern

Every board adapter in `backend/adapters/` implements `JobBoardAdapter` (ABC in `base.py`):
- `search(criteria: SearchCriteria) -> list[JobPosting]`
- Remote-only mapping handled **inside** the adapter (boards express it differently)
- Returns `[]` gracefully when credentials/slugs are absent — never raises
- Use `_safe_iter()` from the base class to skip malformed items without aborting the whole page
- Register new adapters in `backend/adapters/registry.py`

**Greenhouse and Lever** use free public unauthenticated APIs — no API keys needed. Configured via `GREENHOUSE_COMPANIES` / `LEVER_COMPANIES` (comma-separated company slugs). Client-side query filtering uses **whole-word regex** (`\b` boundaries) so short terms like `"ai"` don't match substrings inside unrelated words (`"available"`, `"training"`).

Tests for adapters use recorded JSON fixtures in `tests/adapters/fixtures/` — never hit live boards in CI.

### Frontend data flow

```
Zustand store (useJobSearchStore)  ← global UI state (active IDs, resumeUploaded)
TanStack Query                     ← all server state / cache / polling

Search: SearchForm → POST /search → store activeSearchJobId
        ResultsList polls GET /search/{id}/status every 2s (refetchInterval)
        → when complete, fetches GET /jobs?search_job_id=...

Apply:  JobCard → POST /jobs/{id}/prepare → store activeApplicationId
        ResumeEditor slide-over → DiffView + cover letter preview
        ApprovalScreen → ConfirmationModal → POST /applications/{id}/approve
```

Filter state is synced to URL query params (`window.history.replaceState`) so searches survive refresh.

## Agents

Route work to the right agent:

- `backend-dev` — FastAPI routes, services, LLM orchestration, approval gate
- `react-ui-owner` — all four component areas: SearchForm, ResultsList, ResumeEditor, ApprovalScreen
- `scraper-engineer` — board adapters, rate limiting, normalization
- `test-engineer` — pytest + Vitest, fixture-based adapter tests, approval gate tests
- `code-reviewer` — read-only pre-commit review
- `security-auditor` — read-only security/privacy audit

## Hard invariants

1. **Approval gate**: `application_service.approve_application()` is the **only** function that calls `submission_service.submit()`. It asserts `status == pending` and writes both the status update and the `AuditLog` row in a single `session.commit()`. `submitted_at` is never set without a corresponding `AuditLog` row.

2. **No fabrication**: Resume tailoring and cover letter drafting system prompts contain an absolute prohibition on inventing experience, metrics, employers, or credentials. The prompts are in `backend/llm/prompts/tailor.py` and `drafter.py`.

3. **Prompt injection defense**: `sanitize_jd_text()` runs on all adapter output before any LLM call. System prompts are never formatted with external data. All variable content (including `role_title` and `company`) enters the user turn inside named XML tags.

4. **File upload safety**: Resume upload enforces an extension allowlist (`.pdf`, `.docx`, `.txt`) and a 5 MB size cap before reading content. Violations return HTTP 415 / 413 respectively.

5. **Board compliance**: Adzuna is the live adapter (free official API). Greenhouse and Lever use their free public board APIs (no auth). LinkedIn is not integrated — its ToS prohibits automated access.

## Key conventions

- Route handlers are thin: validate input with Pydantic, call a service, return. Logic lives in `services/`.
- Long-running work (search fan-out, LLM pipeline) runs via `FastAPI BackgroundTasks` — background task functions use `asyncio.run()` since they execute in a thread pool worker, and open their own `Session(engine)`.
- `datetime.now(UTC)` everywhere — `datetime.utcnow()` is deprecated in Python 3.14.
- `bool` columns in SQLModel queries use `== True` with `# noqa: E712` (SQLAlchemy requires the explicit comparison; Python's `is True` doesn't work in WHERE clauses).
- `ApplicationStatus` transitions directly `pending → submitted` (or `failed`). There is no intermediate `approved` state — its absence is intentional to prevent a second submission path from being added.
- Frontend components always handle three data states explicitly: loading, empty, and error.
- The `DiffView` component uses color **and** a text decoration secondary cue (strikethrough for removed, underline for added) — both are required for color-blind accessibility.
