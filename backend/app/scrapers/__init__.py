"""Scraper system for fetching deals from e-commerce platforms.

This package provides:
- Base adapter classes for building shop-specific scrapers
- Utility modules for rate limiting, proxy management, and data normalization
- Factory for creating and managing adapter instances
- Scheduler for automated scraping jobs
"""

from .base import (
    BaseAdapter,
    BaseScraperAdapter,
    BaseAPIAdapter,
    NormalizedProduct,
    NormalizedDeal,
)
from .factory import AdapterFactory, adapter_factory, get_adapter_factory

__all__ = [
    # Base classes
    "BaseAdapter",
    "BaseScraperAdapter",
    "BaseAPIAdapter",
    # Data structures
    "NormalizedProduct",
    "NormalizedDeal",
    # Factory
    "AdapterFactory",
    "adapter_factory",
    "get_adapter_factory",
]
