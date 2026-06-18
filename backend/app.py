import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from backend.config import settings
from backend.limiter import limiter
from backend.logging_config import RequestLoggingMiddleware, configure_logging
from backend.models import insights_cache as _insights_cache_model  # noqa: F401 — registers table
from backend.models import saved_search as _saved_search_model  # noqa: F401 — registers table
from backend.models import user as _user_model  # noqa: F401 — registers table
from backend.routers import (
    applications,
    auth,
    exports,
    insights,
    jobs,
    resume,
    saved_searches,
    search,
)

configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema is owned by Alembic — run `alembic upgrade head` before starting.
    logger.info("startup: ready")
    yield
    logger.info("shutdown: application stopping")


app = FastAPI(title="Job Search Assistant", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RequestLoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Accept", "Authorization"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(resume.router, prefix="/resume", tags=["resume"])
app.include_router(search.router, prefix="/search", tags=["search"])
app.include_router(saved_searches.router, prefix="/saved-searches", tags=["saved-searches"])
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
app.include_router(applications.router, prefix="/applications", tags=["applications"])
app.include_router(exports.router, prefix="/applications", tags=["exports"])
app.include_router(insights.router, prefix="/insights", tags=["insights"])
