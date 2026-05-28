"""Adapter registry: maps source names to adapter classes."""

from backend.adapters.adzuna import AdzunaAdapter
from backend.adapters.base import JobBoardAdapter
from backend.adapters.greenhouse import GreenhouseAdapter
from backend.adapters.lever import LeverAdapter
from backend.adapters.linkedin import LinkedInAdapter
from backend.adapters.remotive import RemotiveAdapter
from backend.adapters.themuse import TheMuseAdapter

ADAPTERS: dict[str, type[JobBoardAdapter]] = {
    "adzuna": AdzunaAdapter,
    "greenhouse": GreenhouseAdapter,
    "lever": LeverAdapter,
    "linkedin": LinkedInAdapter,
    "remotive": RemotiveAdapter,
    "themuse": TheMuseAdapter,
}


def get_all_adapters() -> list[JobBoardAdapter]:
    return [cls() for cls in ADAPTERS.values()]
