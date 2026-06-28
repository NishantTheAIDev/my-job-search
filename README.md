# my-job-search

An AI-powered job search and application assistant. It fans out across many job boards, scores listings against your resume, tailors the resume to each role using Claude, drafts cover letters, and lets you review, edit, and **save** the result for reference. It does **not** submit to job boards — you stay in control of every application. The app is **multi-user**: every account's data is isolated and scoped to its own `user_id`.

## How it works

1. **Register / log in** — create an account; all your resumes, searches, and applications are private to you.
2. **Upload your resume** — the app extracts the text and uses it as the base for all tailoring.
3. **Search for jobs** — fans out concurrently across all configured boards (Adzuna, JSearch, LinkedIn, Indeed, Remotive, The Muse, Greenhouse, Lever, Ashby, Arbeitnow, Jobicy, We Work Remotely, Y Combinator). Results are deduplicated and scored. One board failing never aborts the search.
4. **Prepare an application** — Claude parses the job description, scores your resume against it (0–100), tailors the resume, and drafts a cover letter.
5. **Review & edit** — see a line-by-line diff of resume changes and the cover letter draft; revise either with a follow-up instruction or edit directly.
6. **Save or reject** — save the tailored application for your records, or reject it. Both transitions are audit-logged. **Nothing is ever submitted to a job board.**
7. **Download** — export the tailored resume and cover letter as ATS-safe `.docx` or `.pdf` (the resume PDF supports selectable RenderCV themes).

You also get **job-market insights** (news, salaries, hottest fields, trends by region), **saved searches** with "new since last run" diffing, and a **paste-a-JD** flow to tailor against any posting you supply directly.

## Requirements

- Python 3.14+
- Node.js 20+
- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- [Docker](https://www.docker.com/) (for local Postgres)
- An [Anthropic API key](https://console.anthropic.com/)
- An [Adzuna API key](https://developer.adzuna.com/) (free) — and optionally other board keys (see `.env.example`)

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

Edit `.env` (see the file for the full annotated list):

```env
ANTHROPIC_API_KEY=sk-ant-...        # required
ADZUNA_APP_ID=your_app_id           # recommended for job search
ADZUNA_APP_KEY=your_app_key
JSEARCH_API_KEY=your_rapidapi_key   # optional: LinkedIn/Indeed/Glassdoor aggregator

# Optional: comma-separated company slugs for additional boards (Greenhouse/Lever/Ashby)
GREENHOUSE_COMPANIES=anthropic,databricks,stripe,figma
LEVER_COMPANIES=netflix
ASHBY_COMPANIES=linear

# Database (defaults to the local Docker Postgres below)
# DATABASE_URL=postgresql+psycopg://jobsearch:jobsearch@localhost:5432/jobsearch

# Auth — change this in any non-local deployment
# JWT_SECRET=change-me-in-production
```

Several boards (LinkedIn, Remotive, Arbeitnow, Jobicy, We Work Remotely, Y Combinator, and the Greenhouse/Lever/Ashby public APIs) need no credentials at all. The Y Combinator adapter pulls YC's featured jobs feed with zero config (disable with `YCOMBINATOR_ENABLED=false`).

**Populating YC company slugs:** to fill the Greenhouse/Lever/Ashby slug lists with hiring Y Combinator companies, run the offline resolver — it probes the public board APIs and prints ready-to-paste `*_COMPANIES=` lines:

```bash
make yc-ats-sample            # first 50 hiring YC companies → yc_ats.env (quick)
make yc-ats-sample limit=200  # first 200
make yc-ats                   # all hiring YC companies (slow)
# or directly: uv run python scripts/refresh_yc_ats.py --limit 50 --out yc_ats.env
```

Slug resolution is heuristic (name collisions are possible), so skim `yc_ats.env` before pasting the three lines into `.env`.

### 3. Start Postgres and apply migrations

```bash
docker compose up -d postgres   # local Postgres in Docker
alembic upgrade head            # apply schema migrations
```

`DATABASE_URL` defaults to the local Docker Postgres. At deploy, point it at a managed Postgres (e.g. Supabase/Neon). Tests use in-memory SQLite via a fixture, so models stay DB-agnostic.

### 4. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

## Running the app

Make sure Postgres is up (`docker compose up -d postgres`), then open two terminals from the project root:

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

## Database migrations

The schema is managed with [Alembic](https://alembic.sqlalchemy.org/):

```bash
alembic upgrade head                              # apply all pending migrations
alembic revision --autogenerate -m "describe it"  # generate a migration from model changes
```

## Running tests

Tests run against in-memory SQLite (no Docker/Postgres needed for the test suite).

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

## Linting

**Backend** uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
uv run ruff check .          # check for issues
uv run ruff check --fix .    # check and auto-fix
uv run ruff format .         # format code
```

Rules enabled: `E/W` (pycodestyle), `F` (pyflakes), `I` (isort), `UP` (pyupgrade), `B` (bugbear), `SIM` (simplify). Line length is 100. LLM prompt files and test files are excluded from the line-length rule since prompt prose and fixture assertions are legitimately long.

**Frontend** uses ESLint (configured in `frontend/eslint.config.js`):

```bash
cd frontend
npm run lint
```

## Project structure

```
my-job-search/
├── main.py                     # launches uvicorn
├── pyproject.toml              # backend deps + tool config
├── docker-compose.yml          # local Postgres
├── alembic.ini + alembic/      # database migrations
├── scripts/                    # offline maintenance tools
│   └── refresh_yc_ats.py       # resolve hiring YC companies → ATS slug lists
├── .env.example                # copy to .env and fill in keys
│
├── backend/
│   ├── app.py                  # FastAPI app, middleware, routes
│   ├── config.py               # env-var settings (pydantic-settings)
│   ├── database.py             # Postgres engine + connection pool (SQLModel)
│   ├── limiter.py              # shared slowapi per-user rate limiter
│   ├── logging_config.py       # centralized logging + request IDs
│   ├── auth/                   # JWT security + get_current_user dependency
│   ├── models/                 # SQLModel ORM tables
│   │   ├── user.py             # User account (auth)
│   │   ├── job_posting.py      # JobPosting + SearchCriteria
│   │   ├── resume.py           # Resume (stores path + extracted text)
│   │   ├── search_job.py       # Background search job tracking
│   │   ├── application.py      # Application + state machine (pending→saved/rejected)
│   │   ├── saved_search.py     # Saved search + baseline for diffing
│   │   ├── insights_cache.py   # Cached job-market insights (global, unscoped)
│   │   └── audit_log.py        # Immutable audit trail
│   ├── routers/                # FastAPI route handlers (thin)
│   │   ├── auth.py             # register / login / me
│   │   ├── resume.py, search.py, jobs.py, applications.py
│   │   ├── exports.py          # resume/cover-letter .docx + .pdf downloads
│   │   ├── insights.py         # job-market insights
│   │   └── saved_searches.py   # saved searches + run/diff
│   ├── services/               # Business logic
│   │   ├── search_service.py   # Fan-out, dedup, persist
│   │   ├── scoring_service.py  # Resume × JD → 0-100 score
│   │   ├── tailoring_service.py# Resume tailoring + diff
│   │   ├── drafting_service.py # Cover letter generation
│   │   ├── application_service.py  # Pipeline orchestration; save/reject gate
│   │   ├── rendercv_service.py # RenderCV PDF themes
│   │   ├── saved_search_service.py # Re-run + baseline diffing
│   │   └── insights_service.py + insights/  # Market data orchestration
│   ├── llm/
│   │   ├── client.py           # Anthropic SDK client, retry, prompt caching
│   │   ├── sanitize.py         # Strip control chars from scraped text
│   │   └── prompts/            # System + user prompt templates per skill
│   └── adapters/               # Job board integrations
│       ├── base.py             # JobBoardAdapter ABC
│       ├── registry.py         # Source → adapter mapping
│       ├── adzuna.py jsearch.py linkedin.py indeed.py
│       ├── remotive.py themuse.py arbeitnow.py jobicy.py weworkremotely.py
│       ├── ycombinator.py            # YC featured jobs landing feed (no auth)
│       └── greenhouse.py lever.py ashby.py   # public board APIs (no auth)
│
├── frontend/src/
│   ├── types/index.ts          # TypeScript mirrors of backend schemas
│   ├── api/                    # Typed fetch wrappers per domain
│   ├── store/                  # Zustand global state
│   └── components/
│       ├── Auth/               # Register / login screens
│       ├── Landing/            # Landing page
│       ├── SearchForm + Results/ResultsList/  # Query, filters, job cards
│       ├── ResumeEditor/       # Diff view + cover letter preview
│       ├── ApprovalScreen/     # Final review + save confirmation
│       ├── SavedApplications/  # Saved tailored applications
│       ├── SavedSearches/      # Saved searches + diffing
│       ├── PasteJD/            # Tailor against a pasted job description
│       ├── Insights/           # Job-market insights
│       └── shared/             # DownloadMenu, common UI
│
├── tests/
│   ├── conftest.py             # In-memory SQLite fixtures, test client
│   ├── backend/                # Route + service tests (LLM mocked)
│   └── adapters/               # Adapter tests (HTTP mocked with fixtures)
│       └── fixtures/           # Recorded API responses (no live calls in CI)
│
└── data/                       # Runtime data (gitignored)
    └── resumes/                # Uploaded resume files
```

## API overview

All routes except `/auth/*`, `/insights/*`, and the API docs require a bearer JWT (obtained from register/login). Owned data is scoped per `user_id`; cross-tenant access returns `404`.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/auth/register` | Create an account → bearer JWT |
| `POST` | `/auth/login` | Log in → bearer JWT |
| `GET` | `/auth/me` | Current user |
| `POST` | `/resume/upload` | Upload resume (.pdf, .docx, .txt) |
| `GET` | `/resume` | Get active resume metadata |
| `POST` | `/search` | Start a job search (background) |
| `GET` | `/search/{id}/status` | Poll search progress |
| `GET` | `/jobs` | List results (`?search_job_id=&page=&min_score=&source=&company=`) |
| `GET` | `/jobs/filters` | Distinct sources and companies for a search (`?search_job_id=`) |
| `GET` | `/jobs/{id}` | Get single job posting |
| `POST` | `/jobs/{id}/prepare` | Start LLM pipeline for a job (background) |
| `GET` | `/applications` | List applications (`?status=pending`) |
| `GET` | `/applications/{id}` | Get application with diff + cover letter |
| `POST` | `/applications/{id}/save` | **Save** the tailored application (pending → saved) |
| `POST` | `/applications/{id}/reject` | Reject application (pending → rejected) |
| `POST` | `/applications/{id}/revise` | Revise resume/cover letter with an instruction |
| `PUT` | `/applications/{id}/content` | Directly edit tailored content |
| `GET` | `/applications/{id}/resume.docx` \| `.pdf` | Download tailored resume (`?theme=` on PDF) |
| `GET` | `/applications/{id}/cover-letter.docx` \| `.pdf` | Download cover letter |
| `GET` | `/insights` \| `/insights/salary` | Job-market insights (`?region=`, global/public) |
| `POST` | `/saved-searches` ・ `GET` `/saved-searches` | Create / list saved searches |
| `POST` | `/saved-searches/{id}/run` \| `/diff` | Re-run a saved search; diff vs. baseline |

Full interactive docs: `http://localhost:8000/docs`

## Key design decisions

**No external submission** — the app tailors and **saves** applications; it never submits to job boards. Applications are created `pending`; the only terminal transitions are `pending → saved` and `pending → rejected`, each writing its status change and an `AuditLog` row in one DB transaction. There is intentionally no approve/submit path.

**Tenant isolation** — every query and mutation on an owned entity (`Resume`, `SearchJob`, `JobPosting`, `Application`, `AuditLog`, `SavedSearch`) is scoped to the authenticated `user_id` at the service layer. Cross-tenant access returns `404` so existence can't be probed. `get_current_user` is the single auth seam.

**Prompt injection defense** — all scraped job description text passes through `sanitize_jd_text()` (strips control characters, truncates at 12 000 chars) and is inserted into the user turn only, wrapped in named XML tags. System prompts are never interpolated with external content.

**No fabrication** — resume tailoring and cover letter drafting prompts include an absolute prohibition on inventing experience, metrics, or credentials.

**Adapter pattern** — every job board implements `search(criteria) -> list[JobPosting]`. The search service fans out to all adapters with `asyncio.gather(..., return_exceptions=True)` so one failing board never aborts the entire search. Adapters return `[]` gracefully when credentials are absent.

**Rate limiting** — a shared per-user `slowapi` limiter guards auth, upload, search, and mutation endpoints.

## Adding a new job board

1. Create `backend/adapters/yourboard.py` implementing `JobBoardAdapter`
2. Register it in `backend/adapters/registry.py`
3. Add fixture-based tests in `tests/adapters/test_yourboard_adapter.py` (never hit live boards in CI)
4. Add any needed env vars to `.env.example` and `backend/config.py`

See `backend/adapters/adzuna.py` as a reference and `.claude/skills/job-board-adapter/SKILL.md` for the full contract.
