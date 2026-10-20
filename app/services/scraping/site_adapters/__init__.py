from app.services.scraping.site_adapters.base import BaseSiteAdapter
from app.services.scraping.site_adapters.example_site import WgGesuchtAdapter
from app.services.scraping.site_adapters.registry import AdapterRegistry, adapter_registry

__all__ = [
    "BaseSiteAdapter",
    "WgGesuchtAdapter",
    "AdapterRegistry",
    "adapter_registry",
]
