"""Factory for creating and managing scraper adapter instances."""

from typing import Dict, Optional, Type
import structlog

from app.scrapers.base import BaseAdapter, BaseScraperAdapter, BaseAPIAdapter
from app.scrapers.utils import DomainRateLimiter, ProxyManager, NoProxyManager
from app.config import settings


logger = structlog.get_logger(__name__)


class AdapterFactory:
    """Factory for creating and configuring adapter instances.

    Provides dependency injection for rate limiters, proxy managers,
    and other shared services.
    """

    def __init__(self):
        """Initialize the adapter factory."""
        # Shared rate limiter for all adapters
        self.rate_limiter = DomainRateLimiter()

        # Shared proxy manager
        proxy_list = settings.get_proxy_list()
        if proxy_list:
            self.proxy_manager = ProxyManager(proxy_list)
            logger.info("proxy_manager_initialized", proxy_count=len(proxy_list))
        else:
            self.proxy_manager = NoProxyManager()
            logger.info("proxy_manager_disabled", reason="no_proxies_configured")

        # Registry of adapter classes
        self._adapter_registry: Dict[str, Type[BaseAdapter]] = {}

    def register_adapter(self, shop_slug: str, adapter_class: Type[BaseAdapter]) -> None:
        """Register an adapter class for a shop.

        Args:
            shop_slug: Shop slug identifier (e.g., "coupang")
            adapter_class: Adapter class (must inherit from BaseAdapter)
        """
        if not issubclass(adapter_class, BaseAdapter):
            raise ValueError(f"Adapter class must inherit from BaseAdapter: {adapter_class}")

        self._adapter_registry[shop_slug] = adapter_class
        logger.info("adapter_registered", shop_slug=shop_slug, adapter_type=adapter_class.adapter_type)

    def create_adapter(self, shop_slug: str) -> Optional[BaseAdapter]:
        """Create and configure an adapter instance.

        Args:
            shop_slug: Shop slug identifier

        Returns:
            Configured adapter instance, or None if not registered
        """
        adapter_class = self._adapter_registry.get(shop_slug)
        if not adapter_class:
            logger.warning("adapter_not_found", shop_slug=shop_slug)
            return None

        # Create adapter instance
        adapter = adapter_class()

        # Inject dependencies
        adapter.rate_limiter = self.rate_limiter

        if isinstance(adapter, BaseScraperAdapter):
            adapter.proxy_manager = self.proxy_manager

        logger.info(
            "adapter_created",
            shop_slug=shop_slug,
            adapter_type=adapter.adapter_type,
        )

        return adapter

    def get_registered_shops(self) -> list[str]:
        """Get list of registered shop slugs.

        Returns:
            List of shop slug strings
        """
        return list(self._adapter_registry.keys())

    def has_adapter(self, shop_slug: str) -> bool:
        """Check if an adapter is registered for a shop.

        Args:
            shop_slug: Shop slug identifier

        Returns:
            True if adapter is registered
        """
        return shop_slug in self._adapter_registry


# Global factory instance
adapter_factory = AdapterFactory()


def get_adapter_factory() -> AdapterFactory:
    """Get the global adapter factory instance.

    Returns:
        AdapterFactory instance
    """
    return adapter_factory
