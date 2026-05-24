# my-job-search

An AI-powered job search and application assistant. It searches multiple job boards, scores listings against your resume, tailors the resume to each role using Claude, drafts cover letters, and submits applications — but only after your explicit approval.

## How it works

1. **Upload your resume** — the app extracts the text and uses it as the base for all tailoring.
2. **Search for jobs** — searches Adzuna (and optionally Greenhouse/Lever company boards) concurrently. Results are deduplicated and scored.
3. **Prepare an application** — Claude parses the job description, scores your resume against it (0–100), tailors the resume, and drafts a cover letter.
4. **Review** — see a line-by-line diff of resume changes and the cover letter draft.
5. **Approve** — explicitly confirm before anything is submitted. Every submission is audit-logged.

## Requirements

- Python 3.14+
- Node.js 20+
- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- An [Anthropic API key](https://console.anthropic.com/)
- An [Adzuna API key](https://developer.adzuna.com/) (free)

## Setup

### 1. Clone and install backend dependencies

```bash
git clone <repo-url>
cd my-job-search
uv sync --extra dev
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
ANTHROPIC_API_KEY=sk-ant-...        # required
ADZUNA_APP_ID=your_app_id           # required for job search
ADZUNA_APP_KEY=your_app_key         # required for job search

# Optional: comma-separated company slugs for additional boards
GREENHOUSE_COMPANIES=stripe,notion,figma
LEVER_COMPANIES=stripe,notion
```

### 3. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

## Running the app

Open two terminals from the project root:

**Terminal 1 — backend:**
```bash
uv run main.py
```
API available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

**Terminal 2 — frontend:**
```bash
cd frontend
npm run dev
```
App available at `http://localhost:5173`.

## Running tests

**Backend:**
```bash
uv run pytest                          # all tests
uv run pytest tests/backend/ -v       # backend only
uv run pytest tests/adapters/ -v      # adapter tests only
uv run pytest path/to/test_file.py::test_name  # single test
```

**Frontend:**
```bash
cd frontend
npx vitest run        # run once
npx vitest            # watch mode
```

## Project structure

```
my-job-search/
├── main.py                     # launches uvicorn
├── pyproject.toml              # backend deps + tool config
├── .env.example                # copy to .env and fill in keys
│
├── backend/
│   ├── app.py                  # FastAPI app, middleware, routes
│   ├── config.py               # env-var settings (pydantic-settings)
│   ├── database.py             # SQLite engine (SQLModel)
│   ├── models/                 # SQLModel ORM tables
│   │   ├── job_posting.py      # JobPosting + SearchCriteria
│   │   ├── resume.py           # Resume (stores path + extracted text)
│   │   ├── search_job.py       # Background search job tracking
│   │   ├── application.py      # Application + approval state machine
│   │   └── audit_log.py        # Immutable audit trail
│   ├── routers/                # FastAPI route handlers (thin)
│   ├── services/               # Business logic
│   │   ├── search_service.py   # Fan-out, dedup, persist
│   │   ├── scoring_service.py  # Resume × JD → 0-100 score
│   │   ├── tailoring_service.py# Resume tailoring + diff
│   │   ├── drafting_service.py # Cover letter generation
│   │   ├── application_service.py  # Pipeline orchestration + approval gate
│   │   └── submission_service.py   # Called ONLY from approve_application()
│   ├── llm/
│   │   ├── client.py           # Anthropic SDK client, retry, prompt caching
│   │   ├── sanitize.py         # Strip control chars from scraped text
│   │   └── prompts/            # System + user prompt templates per skill
│   └── adapters/               # Job board integrations
│       ├── base.py             # JobBoardAdapter ABC
│       ├── registry.py         # Source → adapter mapping
│       ├── adzuna.py           # Adzuna REST API (primary)
│       ├── greenhouse.py       # Greenhouse public board API (stub)
│       └── lever.py            # Lever public v0 API (stub)
│
├── frontend/src/
│   ├── types/index.ts          # TypeScript mirrors of backend schemas
│   ├── api/                    # Typed fetch wrappers per domain
│   ├── store/                  # Zustand global state
│   └── components/
│       ├── ResumeUploadBanner/ # Upload UI, blocks search until done
│       ├── SearchForm/         # Query input, filters, remote-only toggle
│       ├── ResultsList/        # Job cards with match scores
│       ├── ResumeEditor/       # Diff view + cover letter preview
│       └── ApprovalScreen/     # Final review + confirmation modal
│
├── tests/
│   ├── conftest.py             # In-memory SQLite fixtures, test client
│   ├── backend/                # Route + service tests (LLM mocked)
│   └── adapters/               # Adapter tests (HTTP mocked with fixtures)
│       └── fixtures/           # Recorded API responses (no live calls in CI)
│
└── data/                       # Runtime data (gitignored)
    ├── jobsearch.db            # SQLite database
    └── resumes/                # Uploaded resume files
```

## API overview

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/resume/upload` | Upload resume (.pdf, .docx, .txt) |
| `GET` | `/resume` | Get active resume metadata |
| `POST` | `/search` | Start a job search (background) |
| `GET` | `/search/{id}/status` | Poll search progress |
| `GET` | `/jobs` | List results (`?search_job_id=&page=&min_score=`) |
| `GET` | `/jobs/{id}` | Get single job posting |
| `POST` | `/jobs/{id}/prepare` | Start LLM pipeline for a job (background) |
| `GET` | `/applications` | List applications (`?status=pending`) |
| `GET` | `/applications/{id}` | Get application with diff + cover letter |
| `POST` | `/applications/{id}/approve` | **Approve and submit** (explicit user action only) |
| `POST` | `/applications/{id}/reject` | Reject application |
| `GET` | `/applications/{id}/resume.docx` | Download tailored resume |

Full interactive docs: `http://localhost:8000/docs`

## Key design decisions

**Approval gate** — applications are created in `pending` state. The only code path to `submitted` is `POST /applications/{id}/approve`. Every submission writes an `AuditLog` row atomically in the same DB transaction. There is no auto-submit anywhere.

**Prompt injection defense** — all scraped job description text passes through `sanitize_jd_text()` (strips control characters, truncates at 12 000 chars) and is inserted into the user turn only, wrapped in `<job_description>` XML tags. System prompts are never interpolated.

**No fabrication** — resume tailoring and cover letter drafting prompts include an absolute prohibition on inventing experience, metrics, or credentials.

**Adapter pattern** — every job board implements `search(criteria) -> list[JobPosting]`. The search service fans out to all adapters with `asyncio.gather(..., return_exceptions=True)` so one failing board never aborts the entire search.

## Adding a new job board

1. Create `backend/adapters/yourboard.py` implementing `JobBoardAdapter`
2. Register it in `backend/adapters/registry.py`
3. Add fixture-based tests in `tests/adapters/test_yourboard_adapter.py` (never hit live boards in CI)
4. Add any needed env vars to `.env.example` and `backend/config.py`

See `backend/adapters/adzuna.py` as a reference and `.claude/skills/job-board-adapter/SKILL.md` for the full contract.
