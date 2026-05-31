"""Adapter registry: maps source names to adapter classes."""

from backend.adapters.adzuna import AdzunaAdapter
from backend.adapters.arbeitnow import ArbeitnowAdapter
from backend.adapters.base import JobBoardAdapter
from backend.adapters.greenhouse import GreenhouseAdapter
from backend.adapters.indeed import IndeedAdapter
from backend.adapters.jobicy import JobicyAdapter
from backend.adapters.jsearch import JSearchAdapter
from backend.adapters.lever import LeverAdapter
from backend.adapters.linkedin import LinkedInAdapter
from backend.adapters.remotive import RemotiveAdapter
from backend.adapters.themuse import TheMuseAdapter
from backend.adapters.weworkremotely import WeWorkRemotelyAdapter

ADAPTERS: dict[str, type[JobBoardAdapter]] = {
    "adzuna": AdzunaAdapter,
    "arbeitnow": ArbeitnowAdapter,
    "greenhouse": GreenhouseAdapter,
    "indeed": IndeedAdapter,
    "jobicy": JobicyAdapter,
    "jsearch": JSearchAdapter,
    "lever": LeverAdapter,
    "linkedin": LinkedInAdapter,
    "remotive": RemotiveAdapter,
    "themuse": TheMuseAdapter,
    "weworkremotely": WeWorkRemotelyAdapter,
}


def get_all_adapters() -> list[JobBoardAdapter]:
    return [cls() for cls in ADAPTERS.values()]
