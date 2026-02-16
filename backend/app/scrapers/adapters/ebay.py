"""eBay Browse API adapter.

Fetches deals from eBay using the eBay Browse API.
Documentation: https://developer.ebay.com/api-docs/buy/browse/overview.html
"""

import httpx
from decimal import Decimal
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

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


class EbayAdapter(BaseAPIAdapter):
    """eBay Browse API adapter for fetching product deals.

    Uses the eBay Browse API with OAuth 2.0 Client Credentials flow.
    Requires EBAY_CLIENT_ID and EBAY_CLIENT_SECRET in environment variables.
    """

    shop_slug = "ebay"
    shop_name = "이베이"
    adapter_type = "api"

    # API Configuration
    API_BASE_URL = "https://api.ebay.com/buy/browse/v1"
    OAUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"
    API_DOMAIN = "api.ebay.com"

    # Category-specific search keywords (English for eBay)
    CATEGORY_KEYWORDS = {
        "pc-hardware": [
            "gaming PC",
            "SSD",
            "graphics card",
            "RAM DDR5",
        ],
        "laptop-mobile": [
            "laptop deal",
            "tablet",
            "smartphone",
        ],
        "electronics-tv": [
            "TV OLED",
            "headphones",
            "robot vacuum",
        ],
        "games-software": [
            "PS5 console",
            "Nintendo Switch",
            "Xbox",
        ],
        "gift-cards": [
            "gift card",
        ],
        "living-food": [
            "smart home",
            "kitchen appliance",
        ],
    }

    def __init__(self):
        """Initialize eBay adapter."""
        super().__init__()
        self.client_id = settings.EBAY_CLIENT_ID
        self.client_secret = settings.EBAY_CLIENT_SECRET

        if not self.client_id or not self.client_secret:
            logger.warning(
                "ebay_credentials_missing",
                message="EBAY_CLIENT_ID or EBAY_CLIENT_SECRET not set",
            )

        # Initialize rate limiter if not injected
        if not self.rate_limiter:
            self.rate_limiter = DomainRateLimiter()
            # eBay allows ~5,000 calls per day = ~3.5 req/min
            # Set to 5 req/min to be safe
            self.rate_limiter.set_custom_limit(self.API_DOMAIN, 5)

        # HTTP client will be created per-request to avoid lifecycle issues
        self._timeout = 30.0

        # OAuth token caching
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    async def fetch_deals(self, category: Optional[str] = None) -> List[NormalizedDeal]:
        """Fetch current deals from eBay Browse API.

        Args:
            category: Optional category filter (e.g., "pc-hardware")
                     If None, fetches deals from all categories.

        Returns:
            List of NormalizedDeal objects

        Raises:
            Exception: If API credentials are missing or API call fails
        """
        if not self.client_id or not self.client_secret:
            raise ValueError(
                "eBay API credentials not configured. "
                "Set EBAY_CLIENT_ID and EBAY_CLIENT_SECRET in .env file."
            )

        deals: List[NormalizedDeal] = []
        seen_item_ids = set()  # For deduplication

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
                        "searching_ebay",
                        category=cat_slug,
                        keyword=keyword,
                    )

                    # Fetch results for this keyword - filter for deals and sort by price
                    results = await self._call_search_api(
                        q=keyword,
                        limit=30,  # Get top 30 results per keyword
                        filter="price:[..1000],priceCurrency:USD",
                        sort="price",  # Sort by price ascending
                    )

                    # Normalize each item
                    for item in results.get("itemSummaries", []):
                        item_id = item.get("itemId")

                        # Skip if already processed (deduplication)
                        if item_id in seen_item_ids:
                            continue

                        # Normalize and add deal
                        try:
                            deal = self._normalize_item(item, category_hint=cat_slug)
                            if deal:
                                deals.append(deal)
                                seen_item_ids.add(item_id)
                        except Exception as e:
                            logger.error(
                                "normalization_failed",
                                item_id=item_id,
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
            "ebay_fetch_complete",
            total_deals=len(deals),
            unique_items=len(seen_item_ids),
            category=category,
        )

        return deals

    async def fetch_product_details(self, external_id: str) -> Optional[NormalizedProduct]:
        """Fetch detailed information for a specific eBay item.

        Args:
            external_id: eBay item ID

        Returns:
            NormalizedProduct or None if not found
        """
        try:
            # Get item details by ID
            item = await self._call_item_api(external_id)

            if not item:
                logger.warning("ebay_product_not_found", item_id=external_id)
                return None

            # Extract price data
            price_data = item.get("price", {})
            current_price_usd = PriceNormalizer.clean_price_string(
                str(price_data.get("value", "0"))
            )

            if not current_price_usd or current_price_usd <= 0:
                logger.warning(
                    "invalid_product_price",
                    item_id=external_id,
                    price=price_data,
                )
                return None

            # Convert USD to KRW
            current_price = PriceNormalizer.to_krw(current_price_usd, "USD")

            # Check for original price (if item has marketing price)
            original_price = None
            marketing_price = item.get("marketingPrice", {}).get("originalPrice", {})
            if marketing_price:
                original_price_usd = PriceNormalizer.clean_price_string(
                    str(marketing_price.get("value", "0"))
                )
                if original_price_usd and original_price_usd > current_price_usd:
                    original_price = PriceNormalizer.to_krw(original_price_usd, "USD")

            title = item.get("title", "")
            image_url = item.get("image", {}).get("imageUrl", "")

            product = NormalizedProduct(
                external_id=str(external_id),
                title=title,
                current_price=current_price,
                original_price=original_price,
                currency="KRW",
                product_url=item.get("itemWebUrl", ""),
                image_url=image_url,
                brand=item.get("brand", None),
                category_hint=CategoryClassifier.classify(title),
                description=item.get("shortDescription", ""),
                metadata={
                    "condition": item.get("condition", ""),
                    "item_location": item.get("itemLocation", {}).get("city", ""),
                    "seller_username": item.get("seller", {}).get("username", ""),
                    "seller_feedback_percentage": item.get("seller", {}).get("feedbackPercentage", ""),
                },
            )

            return product

        except Exception as e:
            logger.error(
                "fetch_ebay_product_failed",
                item_id=external_id,
                error=str(e),
            )
            return None

    async def health_check(self) -> bool:
        """Check if eBay API is accessible and credentials are valid.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Make a simple search call
            await self._call_search_api(q="test", limit=1)
            logger.info("ebay_health_check_passed")
            return True
        except Exception as e:
            logger.error("ebay_health_check_failed", error=str(e))
            return False

    async def _get_access_token(self) -> str:
        """Get OAuth 2.0 access token using Client Credentials flow.

        Caches the token until it expires.

        Returns:
            Access token string

        Raises:
            Exception: If token acquisition fails
        """
        # Return cached token if still valid
        if self._access_token and self._token_expires_at:
            if datetime.utcnow() < self._token_expires_at:
                logger.debug("ebay_using_cached_token")
                return self._access_token

        logger.info("ebay_requesting_new_token")

        # Prepare credentials for Basic Auth
        auth = (self.client_id, self.client_secret)

        # Request body for client credentials grant
        data = {
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope",
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    self.OAUTH_URL,
                    auth=auth,
                    data=data,
                    headers=headers,
                )

                response.raise_for_status()

                token_data = response.json()

                self._access_token = token_data.get("access_token")
                expires_in = token_data.get("expires_in", 7200)  # Default 2 hours

                # Cache token with 5-minute buffer before expiry
                self._token_expires_at = datetime.utcnow() + timedelta(
                    seconds=expires_in - 300
                )

                logger.info(
                    "ebay_token_acquired",
                    expires_in=expires_in,
                )

                return self._access_token

        except Exception as e:
            logger.error("ebay_token_acquisition_failed", error=str(e))
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    )
    async def _call_search_api(
        self,
        q: str,
        limit: int = 30,
        filter: Optional[str] = None,
        sort: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Make a call to the eBay Browse API search endpoint.

        Args:
            q: Search query string
            limit: Number of results to return (max 200)
            filter: Filter criteria (e.g., "price:[..1000],priceCurrency:USD")
            sort: Sort order (e.g., "price" for price ascending)

        Returns:
            API response as dictionary

        Raises:
            httpx.HTTPStatusError: If API returns error status
            httpx.TimeoutException: If request times out
            httpx.NetworkError: If network error occurs
        """
        # Get access token
        token = await self._get_access_token()

        # Rate limiting
        await self.rate_limiter.acquire(self.API_DOMAIN)

        url = f"{self.API_BASE_URL}/item_summary/search"

        # Build query parameters
        params = {
            "q": q,
            "limit": str(min(limit, 200)),  # API max is 200
        }

        if filter:
            params["filter"] = filter
        if sort:
            params["sort"] = sort

        headers = {
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
        }

        logger.debug(
            "ebay_search_api_call",
            query=q,
            limit=params["limit"],
            filter=filter,
            sort=sort,
        )

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, params=params, headers=headers)

                # Handle rate limiting
                if response.status_code == 429:
                    logger.warning("ebay_rate_limit_hit", query=q)
                    raise httpx.HTTPStatusError(
                        "Rate limit exceeded",
                        request=response.request,
                        response=response,
                    )

                # Raise for other HTTP errors
                response.raise_for_status()

                data = response.json()

                items_count = len(data.get("itemSummaries", []))

                logger.debug(
                    "ebay_search_api_success",
                    query=q,
                    returned_items=items_count,
                )

                return data

        except httpx.HTTPStatusError as e:
            logger.error(
                "ebay_search_api_http_error",
                status_code=e.response.status_code,
                query=q,
                error=str(e),
            )
            raise

        except httpx.TimeoutException as e:
            logger.error("ebay_search_api_timeout", query=q, error=str(e))
            raise

        except httpx.NetworkError as e:
            logger.error("ebay_search_api_network_error", query=q, error=str(e))
            raise

        except Exception as e:
            logger.error("ebay_search_api_unexpected_error", query=q, error=str(e))
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    )
    async def _call_item_api(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Make a call to the eBay Browse API item endpoint.

        Args:
            item_id: eBay item ID

        Returns:
            Item data dictionary or None if not found

        Raises:
            httpx.HTTPStatusError: If API returns error status
            httpx.TimeoutException: If request times out
            httpx.NetworkError: If network error occurs
        """
        # Get access token
        token = await self._get_access_token()

        # Rate limiting
        await self.rate_limiter.acquire(self.API_DOMAIN)

        url = f"{self.API_BASE_URL}/item/{item_id}"

        headers = {
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
        }

        logger.debug("ebay_item_api_call", item_id=item_id)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, headers=headers)

                # Handle rate limiting
                if response.status_code == 429:
                    logger.warning("ebay_rate_limit_hit", item_id=item_id)
                    raise httpx.HTTPStatusError(
                        "Rate limit exceeded",
                        request=response.request,
                        response=response,
                    )

                # Handle not found
                if response.status_code == 404:
                    logger.warning("ebay_item_not_found", item_id=item_id)
                    return None

                # Raise for other HTTP errors
                response.raise_for_status()

                data = response.json()

                logger.debug("ebay_item_api_success", item_id=item_id)

                return data

        except httpx.HTTPStatusError as e:
            logger.error(
                "ebay_item_api_http_error",
                status_code=e.response.status_code,
                item_id=item_id,
                error=str(e),
            )
            raise

        except httpx.TimeoutException as e:
            logger.error("ebay_item_api_timeout", item_id=item_id, error=str(e))
            raise

        except httpx.NetworkError as e:
            logger.error("ebay_item_api_network_error", item_id=item_id, error=str(e))
            raise

        except Exception as e:
            logger.error("ebay_item_api_unexpected_error", item_id=item_id, error=str(e))
            raise

    def _normalize_item(
        self, item: Dict[str, Any], category_hint: Optional[str] = None
    ) -> Optional[NormalizedDeal]:
        """Convert eBay API item to NormalizedDeal.

        Args:
            item: Raw item from eBay Browse API response
            category_hint: Optional category hint from search keyword

        Returns:
            NormalizedDeal object or None if item is invalid
        """
        # Extract and clean data
        title = item.get("title", "")
        if not title:
            logger.warning("item_missing_title", item=item)
            return None

        # Parse prices (eBay returns prices in USD)
        price_data = item.get("price", {})
        current_price_usd = PriceNormalizer.clean_price_string(
            str(price_data.get("value", "0"))
        )

        if not current_price_usd or current_price_usd <= 0:
            logger.debug("item_invalid_price", title=title, price=price_data.get("value"))
            return None

        # Convert USD to KRW
        current_price = PriceNormalizer.to_krw(current_price_usd, "USD")

        # Check for marketing/original price
        original_price = None
        discount_percentage = None
        marketing_price = item.get("marketingPrice", {}).get("originalPrice", {})

        if marketing_price:
            original_price_usd = PriceNormalizer.clean_price_string(
                str(marketing_price.get("value", "0"))
            )
            if original_price_usd and original_price_usd > current_price_usd:
                original_price = PriceNormalizer.to_krw(original_price_usd, "USD")
                discount_percentage = self._calculate_discount_percentage(
                    original_price, current_price
                )

        # Determine deal type
        deal_type = "price_drop"
        if discount_percentage:
            if discount_percentage >= 50:
                deal_type = "flash_sale"
            elif discount_percentage >= 20:
                deal_type = "price_drop"

        # Auto-classify category
        classified_category = CategoryClassifier.classify(title)
        # Use category hint from search keyword if classification fails
        if not classified_category:
            classified_category = category_hint

        # Get image URL
        image_url = item.get("image", {}).get("imageUrl", "")

        # Create product
        product = NormalizedProduct(
            external_id=str(item.get("itemId", "")),
            title=title,
            current_price=current_price,
            original_price=original_price,
            currency="KRW",
            product_url=item.get("itemWebUrl", ""),
            image_url=image_url,
            brand=None,  # Not always provided in search results
            category_hint=classified_category,
            description=None,  # Not provided in search API
            metadata={
                "condition": item.get("condition", ""),
                "item_location": item.get("itemLocation", {}).get("city", ""),
                "seller_username": item.get("seller", {}).get("username", ""),
                "seller_feedback_percentage": item.get("seller", {}).get("feedbackPercentage", ""),
                "price_usd": str(current_price_usd),
            },
        )

        # Create deal
        deal = NormalizedDeal(
            product=product,
            deal_price=current_price,
            title=title,
            deal_url=item.get("itemWebUrl", ""),
            original_price=original_price,
            discount_percentage=discount_percentage,
            deal_type=deal_type,
            description=None,
            image_url=image_url,
            starts_at=None,  # Not provided in search API
            expires_at=None,  # Not provided in search API
            metadata={
                "condition": item.get("condition", ""),
                "item_location": item.get("itemLocation", {}).get("city", ""),
                "seller_username": item.get("seller", {}).get("username", ""),
                "seller_feedback_percentage": item.get("seller", {}).get("feedbackPercentage", ""),
            },
        )

        return deal

    async def cleanup(self) -> None:
        """Clean up resources. No persistent resources to clean."""
        pass
