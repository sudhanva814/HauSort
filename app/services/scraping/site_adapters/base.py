from abc import ABC, abstractmethod
from typing import Optional
from app.schemas.scraping import ExtractedPage


class BaseSiteAdapter(ABC):
    """Abstract base class for platform-specific HTML parsing adapters."""

    @abstractmethod
    def supports(self, url: str) -> bool:
        """Returns True if this adapter handles the target listing domain/path."""
        pass

    @abstractmethod
    def extract(self, html: str, url: str) -> Optional[ExtractedPage]:
        """Extracts structured listing content tailored to this website's layout."""
        pass
