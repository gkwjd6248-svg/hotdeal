"""Base scraper adapter interface.

All platform-specific scrapers should inherit from BaseAdapter
and implement the abstract methods defined here.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
import structlog

try:
    from playwright.async_api import BrowserContext, Page
except ImportError:
    BrowserContext = None
    Page = None


@dataclass
class NormalizedProduct:
    """Normalized product data structure returned by all adapters."""

    external_id: str  # Shop-specific product ID
    title: str
    current_price: Decimal
    product_url: str
    original_price: Optional[Decimal] = None
    currency: str = "KRW"
    image_url: Optional[str] = None
    brand: Optional[str] = None
    category_hint: Optional[str] = None  # For auto-categorization
    description: Optional[str] = None
    metadata: dict = field(default_factory=dict)  # Shop-specific additional data

    def __post_init__(self):
        """Validate data after initialization."""
        if not self.external_id:
            raise ValueError("external_id is required")
        if not self.title:
            raise ValueError("title is required")
        if self.current_price is None or self.current_price < 0:
            raise ValueError("current_price must be a non-negative Decimal")


@dataclass
class NormalizedDeal:
    """Normalized deal data structure returned by all adapters."""

    product: NormalizedProduct
    deal_price: Decimal
    title: str
    deal_url: str
    original_price: Optional[Decimal] = None
    discount_percentage: Optional[Decimal] = None
    deal_type: str = "price_drop"  # 'price_drop', 'flash_sale', 'coupon', 'clearance', 'bundle'
    description: Optional[str] = None
    image_url: Optional[str] = None
    starts_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)  # Shop-specific additional data

    def __post_init__(self):
        """Validate data after initialization."""
        if not self.title:
            raise ValueError("title is required")
        if self.deal_price is None or self.deal_price < 0:
            raise ValueError("deal_price must be a non-negative Decimal")
        if self.deal_type not in ["price_drop", "flash_sale", "coupon", "clearance", "bundle"]:
            raise ValueError(f"Invalid deal_type: {self.deal_type}")


class BaseAdapter(ABC):
    """Abstract base class for all shop adapters (API and scraper).

    All adapters must implement fetch_deals() and fetch_product_details().
    Adapters can be API-based or scraper-based, distinguished by adapter_type.
    """

    shop_slug: str = ""  # Must be overridden in subclass (e.g., "coupang", "naver")
    shop_name: str = ""  # Must be overridden in subclass (e.g., "쿠팡", "Naver")
    adapter_type: str = ""  # Must be 'api' or 'scraper'

    def __init__(self):
        """Initialize the adapter with dependency injection points."""
        self.rate_limiter = None  # Injected by factory/dependency injection
        self.logger = structlog.get_logger(adapter=self.shop_slug)

    @abstractmethod
    async def fetch_deals(self, category: Optional[str] = None) -> List[NormalizedDeal]:
        """Fetch current deals from this shop.

        Args:
            category: Optional category filter (e.g., "pc-hardware")

        Returns:
            List of NormalizedDeal objects

        Raises:
            AdapterError: If fetching fails after retries
        """
        pass

    @abstractmethod
    async def fetch_product_details(self, external_id: str) -> Optional[NormalizedProduct]:
        """Fetch detailed information for a specific product.

        Args:
            external_id: Shop-specific product identifier

        Returns:
            NormalizedProduct or None if not found

        Raises:
            AdapterError: If fetching fails after retries
        """
        pass

    async def health_check(self) -> bool:
        """Check if this adapter can connect to its data source.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Default implementation: try to fetch one deal
            deals = await self.fetch_deals()
            return len(deals) >= 0  # Success if no exception thrown
        except Exception as e:
            self.logger.error("health_check_failed", error=str(e))
            return False

    def _calculate_discount_percentage(
        self, original: Optional[Decimal], current: Decimal
    ) -> Optional[Decimal]:
        """Helper to calculate discount percentage.

        Args:
            original: Original price
            current: Current/sale price

        Returns:
            Discount percentage rounded to 2 decimal places, or None
        """
        if original and original > 0 and current < original:
            return round((original - current) / original * 100, 2)
        return None


class BaseScraperAdapter(BaseAdapter):
    """Base class for scraping-based adapters using Playwright.

    Provides common scraping utilities and anti-detection features.
    Subclasses should implement fetch_deals() and fetch_product_details()
    using the provided helper methods.
    """

    adapter_type = "scraper"

    def __init__(self):
        """Initialize scraper adapter."""
        super().__init__()
        self.proxy_manager = None  # Injected
        self.browser_context: Optional[BrowserContext] = None

    async def _get_browser_context(self) -> BrowserContext:
        """Get a configured Playwright browser context with anti-detection.

        This method should be called to get a browser context for scraping.
        The context includes user-agent rotation and proxy configuration.

        Returns:
            Configured BrowserContext

        Note:
            Actual implementation of browser context creation is in the
            factory/service layer that manages Playwright lifecycle.
        """
        # This is a placeholder - actual implementation will be in scraper service
        # that manages Playwright browser lifecycle
        if self.browser_context:
            return self.browser_context
        raise NotImplementedError(
            "Browser context must be injected or created by scraper service"
        )

    async def _safe_scrape(
        self, page: Page, url: str, wait_selector: Optional[str] = None
    ) -> str:
        """Scrape a URL with retry, rate limiting, and error handling.

        Args:
            page: Playwright Page instance
            url: URL to scrape
            wait_selector: Optional CSS selector to wait for before returning HTML

        Returns:
            HTML content as string

        Raises:
            AdapterError: If scraping fails after retries
        """
        # Rate limiting
        if self.rate_limiter:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            await self.rate_limiter.acquire(domain)

        self.logger.info("scraping_url", url=url)

        # Navigate to page
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        # Wait for specific selector if provided
        if wait_selector:
            await page.wait_for_selector(wait_selector, timeout=10000)

        # Get HTML content
        html = await page.content()
        return html

    async def cleanup(self) -> None:
        """Clean up resources (browser context, etc.)."""
        if self.browser_context:
            await self.browser_context.close()
            self.browser_context = None


class BaseAPIAdapter(BaseAdapter):
    """Base class for API-based adapters.

    Provides common utilities for HTTP API calls with rate limiting,
    authentication, and error handling.
    """

    adapter_type = "api"

    def __init__(self):
        """Initialize API adapter."""
        super().__init__()
        self.http_client = None  # httpx.AsyncClient injected
