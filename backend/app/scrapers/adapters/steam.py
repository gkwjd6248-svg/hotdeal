"""Steam Store API adapter.

Fetches game deals from Steam using the unofficial Steam Store API.
Documentation: https://steamapi.xpaw.me/ (community documentation)
"""

import httpx
from decimal import Decimal
from typing import List, Optional, Dict, Any

import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.config import settings
from app.scrapers.base import BaseAPIAdapter, NormalizedDeal, NormalizedProduct
from app.scrapers.utils.normalizer import PriceNormalizer, CategoryClassifier
from app.scrapers.utils.rate_limiter import DomainRateLimiter


logger = structlog.get_logger()


class SteamAdapter(BaseAPIAdapter):
    """Steam Store API adapter for fetching game deals.

    Uses the unofficial Steam Store API to find game deals and specials.
    No authentication required (public API).
    """

    shop_slug = "steam"
    shop_name = "스팀"
    adapter_type = "api"

    # API Configuration
    API_BASE_URL = "https://store.steampowered.com/api"
    API_DOMAIN = "store.steampowered.com"
    FEATURED_ENDPOINT = "/featuredcategories/"
    APP_DETAILS_ENDPOINT = "/appdetails"
    SEARCH_ENDPOINT = "/storesearch/"

    # Search keywords for finding deals (Korean)
    SEARCH_KEYWORDS = [
        "할인",  # Discount
        "세일",  # Sale
        "특가",  # Special price
    ]

    def __init__(self):
        """Initialize Steam adapter."""
        super().__init__()

        # Initialize rate limiter if not injected
        if not self.rate_limiter:
            self.rate_limiter = DomainRateLimiter()
            # Conservative limit: ~10 requests per minute
            self.rate_limiter.set_custom_limit(self.API_DOMAIN, 10)

        # HTTP client will be created per-request to avoid lifecycle issues
        self._timeout = 30.0

    async def fetch_deals(self, category: Optional[str] = None) -> List[NormalizedDeal]:
        """Fetch current deals from Steam Store.

        Args:
            category: Optional category filter (ignored, Steam only has games)
                     Steam deals are always categorized as "games-software"

        Returns:
            List of NormalizedDeal objects

        Raises:
            Exception: If API call fails
        """
        deals: List[NormalizedDeal] = []
        seen_app_ids = set()  # For deduplication

        try:
            logger.info("fetching_steam_featured_deals")

            # Fetch featured categories (includes specials and deals)
            featured_data = await self._call_featured_api()

            # Extract deals from various sections
            specials = featured_data.get("specials", {}).get("items", [])

            logger.info(
                "steam_featured_fetched",
                specials_count=len(specials),
            )

            # Process specials
            for item in specials:
                app_id = item.get("id")
                if app_id in seen_app_ids:
                    continue

                try:
                    deal = self._normalize_featured_item(item)
                    if deal:
                        deals.append(deal)
                        seen_app_ids.add(app_id)
                except Exception as e:
                    logger.error(
                        "normalization_failed",
                        app_id=app_id,
                        error=str(e),
                    )

        except Exception as e:
            logger.error("steam_featured_fetch_failed", error=str(e))
            # Continue even if featured fetch fails

        logger.info(
            "steam_fetch_complete",
            total_deals=len(deals),
            unique_apps=len(seen_app_ids),
        )

        return deals

    async def fetch_product_details(self, external_id: str) -> Optional[NormalizedProduct]:
        """Fetch detailed information for a specific Steam app.

        Args:
            external_id: Steam app ID

        Returns:
            NormalizedProduct or None if not found
        """
        try:
            app_data = await self._call_app_details_api(external_id)

            if not app_data:
                logger.warning("steam_app_not_found", app_id=external_id)
                return None

            # Extract price data
            price_overview = app_data.get("price_overview", {})

            if not price_overview:
                # Free game or not available in region
                logger.debug("steam_app_no_price", app_id=external_id)
                return None

            # Steam returns prices in cents (divided by 100)
            final_price = Decimal(price_overview.get("final", 0)) / 100
            initial_price = Decimal(price_overview.get("initial", 0)) / 100

            if final_price <= 0:
                logger.debug("steam_app_free_or_invalid", app_id=external_id)
                return None

            title = app_data.get("name", "")

            product = NormalizedProduct(
                external_id=str(external_id),
                title=title,
                current_price=final_price,
                original_price=initial_price if initial_price > final_price else None,
                currency="KRW",  # When using cc=KR parameter
                product_url=f"https://store.steampowered.com/app/{external_id}/",
                image_url=app_data.get("header_image", ""),
                brand="Steam",
                category_hint="games-software",
                description=app_data.get("short_description", ""),
                metadata={
                    "type": app_data.get("type", ""),
                    "is_free": app_data.get("is_free", False),
                    "developers": app_data.get("developers", []),
                    "publishers": app_data.get("publishers", []),
                    "platforms": app_data.get("platforms", {}),
                    "categories": [c.get("description") for c in app_data.get("categories", [])],
                    "genres": [g.get("description") for g in app_data.get("genres", [])],
                },
            )

            return product

        except Exception as e:
            logger.error(
                "fetch_steam_product_failed",
                app_id=external_id,
                error=str(e),
            )
            return None

    async def health_check(self) -> bool:
        """Check if Steam API is accessible.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Make a simple API call to featured categories
            await self._call_featured_api()
            logger.info("steam_health_check_passed")
            return True
        except Exception as e:
            logger.error("steam_health_check_failed", error=str(e))
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    )
    async def _call_featured_api(self) -> Dict[str, Any]:
        """Make a call to the Steam Featured Categories API.

        Returns:
            API response as dictionary

        Raises:
            httpx.HTTPStatusError: If API returns error status
            httpx.TimeoutException: If request times out
            httpx.NetworkError: If network error occurs
        """
        # Rate limiting
        await self.rate_limiter.acquire(self.API_DOMAIN)

        url = f"{self.API_BASE_URL}{self.FEATURED_ENDPOINT}"

        # Add parameters for Korean region
        params = {
            "cc": "KR",  # Country code for Korea
            "l": "koreana",  # Language
        }

        logger.debug("steam_featured_api_call")

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, params=params)

                # Handle rate limiting
                if response.status_code == 429:
                    logger.warning("steam_rate_limit_hit")
                    raise httpx.HTTPStatusError(
                        "Rate limit exceeded",
                        request=response.request,
                        response=response,
                    )

                # Raise for other HTTP errors
                response.raise_for_status()

                data = response.json()
                logger.debug("steam_featured_api_success")

                return data

        except httpx.HTTPStatusError as e:
            logger.error(
                "steam_api_http_error",
                status_code=e.response.status_code,
                error=str(e),
            )
            raise

        except httpx.TimeoutException as e:
            logger.error("steam_api_timeout", error=str(e))
            raise

        except httpx.NetworkError as e:
            logger.error("steam_api_network_error", error=str(e))
            raise

        except Exception as e:
            logger.error("steam_api_unexpected_error", error=str(e))
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    )
    async def _call_app_details_api(self, app_id: str) -> Optional[Dict[str, Any]]:
        """Make a call to the Steam App Details API.

        Args:
            app_id: Steam application ID

        Returns:
            App data dictionary or None if not found

        Raises:
            httpx.HTTPStatusError: If API returns error status
            httpx.TimeoutException: If request times out
            httpx.NetworkError: If network error occurs
        """
        # Rate limiting
        await self.rate_limiter.acquire(self.API_DOMAIN)

        url = f"{self.API_BASE_URL}{self.APP_DETAILS_ENDPOINT}"

        params = {
            "appids": app_id,
            "cc": "KR",
            "l": "koreana",
        }

        logger.debug("steam_app_details_call", app_id=app_id)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, params=params)

                # Handle rate limiting
                if response.status_code == 429:
                    logger.warning("steam_rate_limit_hit", app_id=app_id)
                    raise httpx.HTTPStatusError(
                        "Rate limit exceeded",
                        request=response.request,
                        response=response,
                    )

                # Raise for other HTTP errors
                response.raise_for_status()

                data = response.json()

                # Steam API returns {app_id: {success: bool, data: {...}}}
                app_data = data.get(str(app_id), {})

                if not app_data.get("success"):
                    logger.warning("steam_app_not_successful", app_id=app_id)
                    return None

                logger.debug("steam_app_details_success", app_id=app_id)
                return app_data.get("data")

        except httpx.HTTPStatusError as e:
            logger.error(
                "steam_app_details_http_error",
                status_code=e.response.status_code,
                app_id=app_id,
                error=str(e),
            )
            raise

        except httpx.TimeoutException as e:
            logger.error("steam_app_details_timeout", app_id=app_id, error=str(e))
            raise

        except httpx.NetworkError as e:
            logger.error("steam_app_details_network_error", app_id=app_id, error=str(e))
            raise

        except Exception as e:
            logger.error("steam_app_details_unexpected_error", app_id=app_id, error=str(e))
            raise

    def _normalize_featured_item(self, item: Dict[str, Any]) -> Optional[NormalizedDeal]:
        """Convert Steam featured item to NormalizedDeal.

        Args:
            item: Raw item from Steam featured categories API

        Returns:
            NormalizedDeal object or None if item is invalid
        """
        # Extract data
        app_id = str(item.get("id", ""))
        title = item.get("name", "")

        if not app_id or not title:
            logger.warning("steam_item_missing_data", item=item)
            return None

        # Parse prices (Steam returns prices in cents)
        final_price_cents = item.get("final_price", 0)
        original_price_cents = item.get("original_price", 0)

        # Convert from cents to currency units
        final_price = Decimal(final_price_cents) / 100
        original_price = Decimal(original_price_cents) / 100 if original_price_cents else None

        if final_price <= 0:
            logger.debug("steam_item_invalid_price", title=title, app_id=app_id)
            return None

        # Get discount percentage from API
        discount_percent = item.get("discount_percent", 0)
        discount_percentage = Decimal(discount_percent) if discount_percent > 0 else None

        # Determine deal type
        deal_type = "price_drop"
        if discount_percentage:
            if discount_percentage >= 50:
                deal_type = "flash_sale"
            elif discount_percentage >= 20:
                deal_type = "price_drop"

        # Get image URL
        image_url = item.get("header_image", "")
        # If not available, construct from app ID
        if not image_url:
            image_url = f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/header.jpg"

        # Create product
        product = NormalizedProduct(
            external_id=app_id,
            title=title,
            current_price=final_price,
            original_price=original_price,
            currency="KRW",
            product_url=f"https://store.steampowered.com/app/{app_id}/",
            image_url=image_url,
            brand="Steam",
            category_hint="games-software",
            description=None,  # Not provided in featured API
            metadata={
                "type": item.get("type", ""),
                "controller_support": item.get("controller_support", ""),
                "platforms": {
                    "windows": item.get("windows_available", False),
                    "mac": item.get("mac_available", False),
                    "linux": item.get("linux_available", False),
                },
            },
        )

        # Create deal
        deal = NormalizedDeal(
            product=product,
            deal_price=final_price,
            title=title,
            deal_url=f"https://store.steampowered.com/app/{app_id}/",
            original_price=original_price,
            discount_percentage=discount_percentage,
            deal_type=deal_type,
            description=None,
            image_url=image_url,
            starts_at=None,  # Not provided
            expires_at=None,  # Not provided
            metadata={
                "discount_percent": discount_percent,
                "type": item.get("type", ""),
                "platforms": {
                    "windows": item.get("windows_available", False),
                    "mac": item.get("mac_available", False),
                    "linux": item.get("linux_available", False),
                },
            },
        )

        return deal

    async def cleanup(self) -> None:
        """Clean up resources. No persistent resources to clean."""
        pass
