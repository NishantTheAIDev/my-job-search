"""Insights router — job market news, salaries, hottest fields, and hiring trends."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlmodel import Session

from backend.database import get_session
from backend.limiter import limiter
from backend.services.insights_service import get_insights, get_salary

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class NewsItem(BaseModel):
    title: str
    url: str
    domain: str
    seendate: str


class SalaryStat(BaseModel):
    role: str
    median: float | None
    currency: str
    sample_size: int


class HotField(BaseModel):
    label: str
    tag: str
    openings: int
    mean_salary: float | None
    currency: str


class TrendPoint(BaseModel):
    period: str
    value: float


class MacroPoint(BaseModel):
    year: int
    value: float


class TrendData(BaseModel):
    salary_history: list[TrendPoint]
    unemployment: list[MacroPoint]
    employment: list[MacroPoint]


class InsightsResponse(BaseModel):
    region: str
    currency: str
    generated_at: datetime
    news: list[NewsItem]
    salaries: list[SalaryStat]
    hottest_fields: list[HotField]
    trends: TrendData


class SalaryResponse(BaseModel):
    role: str
    median: float | None
    currency: str
    sample_size: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=InsightsResponse)
@limiter.limit("10/minute")
async def insights(
    request: Request,
    region: str = Query(default="in", description="Region code: in, us, gb, world"),
    session: Session = Depends(get_session),
) -> InsightsResponse:
    """Return job-market insights for the given region.

    Sections: news (Google News RSS + Hacker News fallback), salaries (Adzuna histogram
    median), hottest_fields
    (Adzuna categories ranked by vacancy count), trends (Adzuna history +
    World Bank macro). Each section is cached server-side for ~24 h.
    """
    try:
        data = await get_insights(region, session)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    trends_raw = data.get("trends") or {}
    trend_data = TrendData(
        salary_history=[TrendPoint(**p) for p in trends_raw.get("salary_history", [])],
        unemployment=[MacroPoint(**p) for p in trends_raw.get("unemployment", [])],
        employment=[MacroPoint(**p) for p in trends_raw.get("employment", [])],
    )

    return InsightsResponse(
        region=data["region"],
        currency=data["currency"],
        generated_at=data["generated_at"],
        news=[NewsItem(**n) for n in data.get("news", [])],
        salaries=[SalaryStat(**s) for s in data.get("salaries", [])],
        hottest_fields=[HotField(**f) for f in data.get("hottest_fields", [])],
        trends=trend_data,
    )


@router.get("/salary", response_model=SalaryResponse)
@limiter.limit("20/minute")
async def salary_lookup(
    request: Request,
    role: str = Query(..., min_length=1, max_length=200, description="Job role to look up"),
    region: str = Query(default="in", description="Region code: in, us, gb, world"),
    session: Session = Depends(get_session),
) -> SalaryResponse:
    """On-demand salary lookup for a single role.

    Hits Adzuna histogram to compute a median. Results are cached.
    """
    try:
        data = await get_salary(role, region, session)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SalaryResponse(**data)
