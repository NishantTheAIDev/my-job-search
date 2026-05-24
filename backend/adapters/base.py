"""JobBoardAdapter ABC and _safe_iter helper."""
import logging
from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any

from backend.models.job_posting import JobPosting, SearchCriteria

logger = logging.getLogger(__name__)


class JobBoardAdapter(ABC):
    source: str  # class-level constant, e.g. "adzuna"

    @abstractmethod
    async def search(self, criteria: SearchCriteria) -> list[JobPosting]:
        """Search the board and return normalized postings."""
        ...

    def _safe_iter(self, items: list[Any]) -> Iterator[Any]:
        """Yield items one by one; log and skip anything that causes an error."""
        for item in items:
            try:
                yield item
            except Exception as exc:
                logger.warning("skipping unparseable item from %s: %s", self.source, exc)
