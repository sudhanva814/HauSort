from typing import List, Optional

from app.services.scraping.site_adapters.base import BaseSiteAdapter
from app.services.scraping.site_adapters.example_site import WgGesuchtAdapter


class AdapterRegistry:
    """Registry maintaining available site-specific scraping adapters."""

    def __init__(self):
        self._adapters: List[BaseSiteAdapter] = [
            WgGesuchtAdapter(),
        ]

    def register(self, adapter: BaseSiteAdapter) -> None:
        """Register a new adapter."""
        self._adapters.append(adapter)

    def get_adapter(self, url: str) -> Optional[BaseSiteAdapter]:
        """Finds the first adapter supporting the given URL."""
        for adapter in self._adapters:
            if adapter.supports(url):
                return adapter
        return None


# Global registry instance
adapter_registry = AdapterRegistry()
