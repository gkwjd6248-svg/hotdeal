"""Newegg deals scraper adapter.

Fetches deals from Newegg using their public web API endpoints.
No official API, but uses JSON endpoints from their deals and search pages.
"""

import httpx
from decimal import Decimal
from typing import List, Optional, Dict, Any
from datetime import datetime

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


class NeweggAdapter(BaseAPIAdapter):
    """Newegg deals scraper adapter using public JSON endpoints.

    Uses Newegg's public AJAX/JSON endpoints for deals and search.
    No authentication required, but needs realistic browser headers.
    """

    shop_slug = "newegg"
    shop_name = "뉴에그"
    adapter_type = "api"

    # API Configuration
    DEALS_API_URL = "https://www.newegg.com/api/Deal/Deals"
    SEARCH_API_URL = "https://www.newegg.com/product/api/search"
    API_DOMAIN = "www.newegg.com"

    # Category-specific search keywords (in English for US site)
    CATEGORY_KEYWORDS = {
        "pc-hardware": [
            "graphics card RTX",
            "SSD NVMe",
            "DDR5 RAM",
            "gaming motherboard",
            "CPU Ryzen",
            "PSU 850W",
        ],
        "laptop-mobile": [
            "gaming laptop",
            "ultrabook",
            "laptop RTX",
            "business laptop",
        ],
        "electronics-tv": [
            "4K monitor",
            "gaming monitor 144Hz",
            "wireless headphones",
            "mechanical keyboard",
        ],
        "games-software": [
            "gaming console",
            "PC game",
            "gaming chair",
            "gaming desk",
        ],
    }

    def __init__(self):
        """Initialize Newegg adapter."""
        super().__init__()

        # Initialize rate limiter if not injected
        if not self.rate_limiter:
            self.rate_limiter = DomainRateLimiter()
            # Conservative rate limit: 15 requests per minute
            self.rate_limiter.set_custom_limit(self.API_DOMAIN, 15)

        # HTTP client will be created per-request to avoid lifecycle issues
        self._timeout = 30.0

        # Realistic browser headers to avoid detection
        self._headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.newegg.com/",
            "Origin": "https://www.newegg.com",
            "DNT": "1",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }

    async def fetch_deals(self, category: Optional[str] = None) -> List[NormalizedDeal]:
        """Fetch current deals from Newegg.

        Args:
            category: Optional category filter (e.g., "pc-hardware")
                     If None, fetches deals from all categories.

        Returns:
            List of NormalizedDeal objects

        Raises:
            Exception: If API call fails after retries
        """
        deals: List[NormalizedDeal] = []
        seen_item_numbers = set()  # For deduplication

        # First, fetch shell deals (today's deals page)
        try:
            logger.info("fetching_newegg_shell_deals")
            shell_deals = await self._fetch_shell_deals()

            for item in shell_deals:
                item_number = item.get("ItemNumber")
                if item_number and item_number not in seen_item_numbers:
                    try:
                        deal = self._normalize_item(item)
                        if deal:
                            deals.append(deal)
                            seen_item_numbers.add(item_number)
                    except Exception as e:
                        logger.error(
                            "normalization_failed",
                            item_number=item_number,
                            error=str(e),
                        )

        except Exception as e:
            logger.error("shell_deals_fetch_failed", error=str(e))
            # Continue to search even if shell deals fail

        # Determine which keywords to search
        if category and category in self.CATEGORY_KEYWORDS:
            keyword_groups = {category: self.CATEGORY_KEYWORDS[category]}
        elif category:
            logger.warning(
                "unknown_category",
                category=category,
                message="Category not found in keyword map, searching all categories",
            )
            keyword_groups = self.CATEGORY_KEYWORDS
        else:
            keyword_groups = self.CATEGORY_KEYWORDS

        # Search for each keyword
        for cat_slug, keywords in keyword_groups.items():
            for keyword in keywords:
                try:
                    logger.info(
                        "searching_newegg",
                        category=cat_slug,
                        keyword=keyword,
                    )

                    # Fetch results for this keyword
                    results = await self._search_products(keyword, page_size=36)

                    # Normalize each item
                    for item in results:
                        item_number = item.get("ItemNumber")

                        # Skip if already processed (deduplication)
                        if item_number in seen_item_numbers:
                            continue

                        try:
                            deal = self._normalize_item(item, category_hint=cat_slug)
                            if deal:
                                deals.append(deal)
                                seen_item_numbers.add(item_number)
                        except Exception as e:
                            logger.error(
                                "normalization_failed",
                                item_number=item_number,
                                error=str(e),
                            )

                except Exception as e:
                    logger.error(
                        "keyword_search_failed",
                        keyword=keyword,
                        error=str(e),
                    )
                    # Continue with next keyword even if one fails

        logger.info(
            "newegg_fetch_complete",
            total_deals=len(deals),
            unique_items=len(seen_item_numbers),
            category=category,
        )

        return deals

    async def fetch_product_details(self, external_id: str) -> Optional[NormalizedProduct]:
        """Fetch detailed information for a specific product.

        Args:
            external_id: Newegg item number

        Returns:
            NormalizedProduct or None if not found
        """
        try:
            # Search by item number
            results = await self._search_products(external_id, page_size=1)

            if not results:
                logger.warning("product_not_found", item_number=external_id)
                return None

            item = results[0]

            # Verify this is the correct item
            if item.get("ItemNumber") != external_id:
                logger.warning(
                    "product_mismatch",
                    requested=external_id,
                    found=item.get("ItemNumber"),
                )
                return None

            # Extract pricing
            pricing = item.get("Pricing", {})
            current_price_usd = self._extract_price(pricing.get("FinalPrice"))
            original_price_usd = self._extract_price(pricing.get("OriginalPrice"))

            if not current_price_usd or current_price_usd <= 0:
                logger.warning(
                    "invalid_product_price",
                    item_number=external_id,
                    price=pricing.get("FinalPrice"),
                )
                return None

            # Convert USD to KRW
            current_price = PriceNormalizer.to_krw(current_price_usd, "USD")
            original_price = None
            if original_price_usd and original_price_usd > current_price_usd:
                original_price = PriceNormalizer.to_krw(original_price_usd, "USD")

            title = item.get("Title", "").strip()
            if not title:
                logger.warning("product_missing_title", item_number=external_id)
                return None

            product = NormalizedProduct(
                external_id=str(external_id),
                title=title,
                current_price=current_price,
                original_price=original_price,
                currency="KRW",
                product_url=f"https://www.newegg.com/p/{external_id}",
                image_url=item.get("ImagePath", ""),
                brand=item.get("BrandName", "") or None,
                category_hint=CategoryClassifier.classify(title),
                description=item.get("Description", "") or None,
                metadata={
                    "item_number": external_id,
                    "rating": item.get("Rating"),
                    "review_count": item.get("ReviewCount"),
                    "shipping": pricing.get("ShippingPrice"),
                    "is_featured": item.get("IsFeatured", False),
                },
            )

            return product

        except Exception as e:
            logger.error(
                "fetch_product_failed",
                item_number=external_id,
                error=str(e),
            )
            return None

    async def health_check(self) -> bool:
        """Check if Newegg API is accessible.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Try to fetch shell deals
            deals = await self._fetch_shell_deals()
            logger.info("newegg_health_check_passed", deals_count=len(deals))
            return True
        except Exception as e:
            logger.error("newegg_health_check_failed", error=str(e))
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    )
    async def _fetch_shell_deals(
        self, page_size: int = 36, page_no: int = 1
    ) -> List[Dict[str, Any]]:
        """Fetch deals from Newegg's Shell Deals page.

        Args:
            page_size: Number of results per page (default 36)
            page_no: Page number (1-based)

        Returns:
            List of deal items

        Raises:
            httpx.HTTPStatusError: If API returns error status
            httpx.TimeoutException: If request times out
            httpx.NetworkError: If network error occurs
        """
        # Rate limiting
        await self.rate_limiter.acquire(self.API_DOMAIN)

        params = {
            "storeType": 0,
            "pageSize": page_size,
            "nodeId": 0,
            "pageNo": page_no,
        }

        logger.debug("newegg_shell_deals_api_call", page_size=page_size, page_no=page_no)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    self.DEALS_API_URL,
                    headers=self._headers,
                    params=params,
                )

                # Handle errors
                if response.status_code == 429:
                    logger.warning("newegg_rate_limit_hit")
                    raise httpx.HTTPStatusError(
                        "Rate limit exceeded",
                        request=response.request,
                        response=response,
                    )

                response.raise_for_status()

                data = response.json()

                # Extract deals from response structure
                deals = []
                if isinstance(data, dict):
                    # Response structure may vary, check common paths
                    deals = data.get("ItemList", []) or data.get("items", []) or []
                elif isinstance(data, list):
                    deals = data

                logger.debug(
                    "newegg_shell_deals_success",
                    returned_items=len(deals),
                )

                return deals

        except httpx.HTTPStatusError as e:
            logger.error(
                "newegg_shell_deals_http_error",
                status_code=e.response.status_code,
                error=str(e),
            )
            raise

        except httpx.TimeoutException as e:
            logger.error("newegg_shell_deals_timeout", error=str(e))
            raise

        except httpx.NetworkError as e:
            logger.error("newegg_shell_deals_network_error", error=str(e))
            raise

        except Exception as e:
            logger.error("newegg_shell_deals_unexpected_error", error=str(e))
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    )
    async def _search_products(
        self, keyword: str, page_size: int = 36, page_number: int = 1
    ) -> List[Dict[str, Any]]:
        """Search Newegg products using their search API.

        Args:
            keyword: Search keyword
            page_size: Number of results per page (default 36)
            page_number: Page number (1-based)

        Returns:
            List of product items

        Raises:
            httpx.HTTPStatusError: If API returns error status
            httpx.TimeoutException: If request times out
            httpx.NetworkError: If network error occurs
        """
        # Rate limiting
        await self.rate_limiter.acquire(self.API_DOMAIN)

        params = {
            "Description": keyword,
            "PageSize": page_size,
            "PageNumber": page_number,
            "IsUPCCodeSearch": False,
        }

        logger.debug(
            "newegg_search_api_call",
            keyword=keyword,
            page_size=page_size,
        )

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    self.SEARCH_API_URL,
                    headers=self._headers,
                    params=params,
                )

                # Handle errors
                if response.status_code == 429:
                    logger.warning("newegg_rate_limit_hit", keyword=keyword)
                    raise httpx.HTTPStatusError(
                        "Rate limit exceeded",
                        request=response.request,
                        response=response,
                    )

                response.raise_for_status()

                data = response.json()

                # Extract items from response structure
                items = []
                if isinstance(data, dict):
                    # Common response paths
                    items = (
                        data.get("ItemList", [])
                        or data.get("ProductListItems", [])
                        or data.get("items", [])
                        or []
                    )
                elif isinstance(data, list):
                    items = data

                logger.debug(
                    "newegg_search_success",
                    keyword=keyword,
                    returned_items=len(items),
                )

                return items

        except httpx.HTTPStatusError as e:
            logger.error(
                "newegg_search_http_error",
                status_code=e.response.status_code,
                keyword=keyword,
                error=str(e),
            )
            raise

        except httpx.TimeoutException as e:
            logger.error("newegg_search_timeout", keyword=keyword, error=str(e))
            raise

        except httpx.NetworkError as e:
            logger.error("newegg_search_network_error", keyword=keyword, error=str(e))
            raise

        except Exception as e:
            logger.error("newegg_search_unexpected_error", keyword=keyword, error=str(e))
            raise

    def _normalize_item(
        self, item: Dict[str, Any], category_hint: Optional[str] = None
    ) -> Optional[NormalizedDeal]:
        """Convert Newegg API item to NormalizedDeal.

        Args:
            item: Raw item from Newegg API response
            category_hint: Optional category hint from search keyword

        Returns:
            NormalizedDeal object or None if item is invalid
        """
        # Extract title
        title = item.get("Title", "").strip()
        if not title:
            logger.warning("item_missing_title", item=item)
            return None

        # Extract pricing (Newegg returns nested Pricing object)
        pricing = item.get("Pricing", {})
        if not pricing:
            logger.debug("item_missing_pricing", title=title)
            return None

        # Parse prices in USD
        final_price_usd = self._extract_price(pricing.get("FinalPrice"))
        original_price_usd = self._extract_price(pricing.get("OriginalPrice"))

        if not final_price_usd or final_price_usd <= 0:
            logger.debug("item_invalid_price", title=title, price=pricing.get("FinalPrice"))
            return None

        # Convert USD to KRW
        final_price = PriceNormalizer.to_krw(final_price_usd, "USD")
        original_price = None
        discount_percentage = None

        if original_price_usd and original_price_usd > final_price_usd:
            original_price = PriceNormalizer.to_krw(original_price_usd, "USD")
            discount_percentage = self._calculate_discount_percentage(
                original_price, final_price
            )

        # Determine deal type
        deal_type = "price_drop"
        if discount_percentage:
            if discount_percentage >= 30:
                deal_type = "flash_sale"
            elif discount_percentage >= 10:
                deal_type = "price_drop"
        elif item.get("IsFeatured"):
            deal_type = "flash_sale"

        # Auto-classify category
        classified_category = CategoryClassifier.classify(title)
        # Use category hint from search keyword if classification fails
        if not classified_category:
            classified_category = category_hint

        # Extract item number
        item_number = item.get("ItemNumber", "")
        if not item_number:
            logger.warning("item_missing_number", title=title)
            return None

        # Build product URL
        product_url = f"https://www.newegg.com/p/{item_number}"

        # Create product
        product = NormalizedProduct(
            external_id=str(item_number),
            title=title,
            current_price=final_price,
            original_price=original_price,
            currency="KRW",
            product_url=product_url,
            image_url=item.get("ImagePath", ""),
            brand=item.get("BrandName", "") or None,
            category_hint=classified_category,
            description=item.get("Description", "") or None,
            metadata={
                "item_number": item_number,
                "rating": item.get("Rating"),
                "review_count": item.get("ReviewCount"),
                "is_featured": item.get("IsFeatured", False),
                "shipping_usd": pricing.get("ShippingPrice"),
            },
        )

        # Create deal
        deal = NormalizedDeal(
            product=product,
            deal_price=final_price,
            title=title,
            deal_url=product_url,
            original_price=original_price,
            discount_percentage=discount_percentage,
            deal_type=deal_type,
            description=item.get("Description", "") or None,
            image_url=item.get("ImagePath", ""),
            starts_at=None,  # Newegg doesn't provide deal timestamps
            expires_at=None,
            metadata={
                "item_number": item_number,
                "brand": item.get("BrandName", ""),
                "rating": item.get("Rating"),
                "review_count": item.get("ReviewCount"),
                "is_featured": item.get("IsFeatured", False),
                "original_price_usd": str(original_price_usd) if original_price_usd else None,
                "final_price_usd": str(final_price_usd),
            },
        )

        return deal

    @staticmethod
    def _extract_price(price_value: Any) -> Optional[Decimal]:
        """Extract price from Newegg price field.

        Newegg prices can be strings ("$123.99") or floats (123.99).

        Args:
            price_value: Price value from API

        Returns:
            Decimal price in USD, or None if invalid
        """
        if not price_value:
            return None

        # If it's already a number
        if isinstance(price_value, (int, float)):
            try:
                return Decimal(str(price_value))
            except Exception:
                return None

        # If it's a string, clean and parse
        if isinstance(price_value, str):
            cleaned = PriceNormalizer.clean_price_string(price_value)
            return cleaned

        return None

    async def cleanup(self) -> None:
        """Clean up resources. No persistent resources to clean."""
        pass
