"""Coupang Partners API adapter.

Fetches deals from Coupang using the Coupang Partners API.
Documentation: https://developers.coupangcorp.com/
"""

import hmac
import hashlib
import httpx
from decimal import Decimal
from typing import List, Optional, Dict, Any
from datetime import datetime
from urllib.parse import urljoin

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


class CoupangAdapter(BaseAPIAdapter):
    """Coupang Partners API adapter for fetching product deals.

    Uses the Coupang Partners API to find deals across multiple categories.
    Requires COUPANG_ACCESS_KEY and COUPANG_SECRET_KEY in environment variables.
    """

    shop_slug = "coupang"
    shop_name = "쿠팡"
    adapter_type = "api"

    # API Configuration
    API_BASE_URL = "https://api-gateway.coupang.com"
    API_DOMAIN = "api-gateway.coupang.com"
    SEARCH_ENDPOINT = "/v2/providers/affiliate_open_api/apis/openapi/products/search"

    # Category-specific search keywords (similar to Naver)
    CATEGORY_KEYWORDS = {
        "pc-hardware": [
            "그래픽카드 특가",
            "SSD 할인",
            "CPU 특가",
            "RAM DDR5 할인",
            "메인보드 특가",
        ],
        "laptop-mobile": [
            "노트북 특가",
            "스마트폰 할인",
            "태블릿 특가",
            "갤럭시 할인",
        ],
        "electronics-tv": [
            "TV 특가",
            "모니터 할인",
            "세탁기 특가",
            "에어컨 할인",
            "냉장고 특가",
        ],
        "games-software": [
            "게임 특가",
            "PS5 할인",
            "닌텐도 특가",
        ],
        "gift-cards": [
            "상품권 할인",
            "기프트카드 특가",
        ],
        "living-food": [
            "식품 특가",
            "생활용품 할인",
            "건강식품 특가",
        ],
    }

    def __init__(self):
        """Initialize Coupang Partners adapter."""
        super().__init__()
        self.access_key = settings.COUPANG_ACCESS_KEY
        self.secret_key = settings.COUPANG_SECRET_KEY

        if not self.access_key or not self.secret_key:
            logger.warning(
                "coupang_credentials_missing",
                message="COUPANG_ACCESS_KEY or COUPANG_SECRET_KEY not set",
            )

        # Initialize rate limiter if not injected
        if not self.rate_limiter:
            self.rate_limiter = DomainRateLimiter()
            # Conservative limit: ~60 requests per minute
            self.rate_limiter.set_custom_limit(self.API_DOMAIN, 60)

        # HTTP client will be created per-request to avoid lifecycle issues
        self._timeout = 30.0

    async def fetch_deals(self, category: Optional[str] = None) -> List[NormalizedDeal]:
        """Fetch current deals from Coupang Partners API.

        Args:
            category: Optional category filter (e.g., "pc-hardware")
                     If None, fetches deals from all categories.

        Returns:
            List of NormalizedDeal objects

        Raises:
            Exception: If API credentials are missing or API call fails
        """
        if not self.access_key or not self.secret_key:
            raise ValueError(
                "Coupang API credentials not configured. "
                "Set COUPANG_ACCESS_KEY and COUPANG_SECRET_KEY in .env file."
            )

        deals: List[NormalizedDeal] = []
        seen_product_ids = set()  # For deduplication

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
                        "searching_coupang",
                        category=cat_slug,
                        keyword=keyword,
                    )

                    # Fetch results for this keyword
                    results = await self._call_api(
                        keyword=keyword,
                        limit=30,  # Get top 30 results per keyword
                    )

                    # Normalize each item
                    for item in results.get("data", []):
                        product_id = item.get("productId")

                        # Skip if already processed (deduplication)
                        if product_id in seen_product_ids:
                            continue

                        # Normalize and add deal
                        try:
                            deal = self._normalize_item(item, category_hint=cat_slug)
                            if deal:
                                deals.append(deal)
                                seen_product_ids.add(product_id)
                        except Exception as e:
                            logger.error(
                                "normalization_failed",
                                product_id=product_id,
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
            "coupang_fetch_complete",
            total_deals=len(deals),
            unique_products=len(seen_product_ids),
            category=category,
        )

        return deals

    async def fetch_product_details(self, external_id: str) -> Optional[NormalizedProduct]:
        """Fetch detailed information for a specific product.

        Args:
            external_id: Coupang product ID

        Returns:
            NormalizedProduct or None if not found
        """
        try:
            # Search by product ID
            results = await self._call_api(
                keyword=external_id,
                limit=1,
            )

            items = results.get("data", [])
            if not items:
                logger.warning("product_not_found", product_id=external_id)
                return None

            item = items[0]

            # Create normalized product
            title = item.get("productName", "")
            product_price = PriceNormalizer.clean_price_string(
                str(item.get("productPrice", "0"))
            )

            if not product_price or product_price <= 0:
                logger.warning(
                    "invalid_product_price",
                    product_id=external_id,
                    product_price=item.get("productPrice"),
                )
                return None

            product = NormalizedProduct(
                external_id=str(item.get("productId", external_id)),
                title=title,
                current_price=product_price,
                original_price=None,  # Coupang API doesn't always provide original price in list
                currency="KRW",
                product_url=item.get("productUrl", ""),
                image_url=item.get("productImage", ""),
                brand=None,  # Not provided in search API
                category_hint=CategoryClassifier.classify(title),
                description=None,  # Not provided in search API
                metadata={
                    "category_name": item.get("categoryName", ""),
                    "is_rocket": item.get("isRocket", False),
                    "is_fresh": item.get("isFresh", False),
                    "free_shipping": item.get("freeShipping", False),
                },
            )

            return product

        except Exception as e:
            logger.error(
                "fetch_product_failed",
                product_id=external_id,
                error=str(e),
            )
            return None

    async def health_check(self) -> bool:
        """Check if Coupang API is accessible and credentials are valid.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Make a simple API call with a generic search term
            await self._call_api(keyword="테스트", limit=1)
            logger.info("coupang_health_check_passed")
            return True
        except Exception as e:
            logger.error("coupang_health_check_failed", error=str(e))
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    )
    async def _call_api(
        self,
        keyword: str,
        limit: int = 30,
        sub_id: str = "dealhawk",
    ) -> Dict[str, Any]:
        """Make a call to the Coupang Partners API with retry logic.

        Args:
            keyword: Search query string
            limit: Number of results to return (max 100)
            sub_id: Sub ID for tracking (optional)

        Returns:
            API response as dictionary

        Raises:
            httpx.HTTPStatusError: If API returns error status
            httpx.TimeoutException: If request times out
            httpx.NetworkError: If network error occurs
        """
        # Rate limiting
        await self.rate_limiter.acquire(self.API_DOMAIN)

        # Build request URL
        url = urljoin(self.API_BASE_URL, self.SEARCH_ENDPOINT)
        params = {
            "keyword": keyword,
            "limit": min(limit, 100),  # API max is 100
            "subId": sub_id,
        }

        # Generate request signature
        request_method = "GET"
        request_path = self.SEARCH_ENDPOINT + self._build_query_string(params)
        utc_now = datetime.utcnow()
        datetime_str = utc_now.strftime("%y%m%dT%H%M%SZ")

        headers = self._generate_auth_headers(
            method=request_method,
            path=request_path,
            datetime_str=datetime_str,
        )

        logger.debug(
            "coupang_api_call",
            keyword=keyword,
            limit=params["limit"],
        )

        # Make request using context manager for proper cleanup
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    url,
                    headers=headers,
                    params=params,
                )

                # Handle rate limiting
                if response.status_code == 429:
                    logger.warning("coupang_rate_limit_hit", keyword=keyword)
                    raise httpx.HTTPStatusError(
                        "Rate limit exceeded",
                        request=response.request,
                        response=response,
                    )

                # Raise for other HTTP errors
                response.raise_for_status()

                data = response.json()
                logger.debug(
                    "coupang_api_success",
                    keyword=keyword,
                    returned_items=len(data.get("data", [])),
                )

                return data

        except httpx.HTTPStatusError as e:
            logger.error(
                "coupang_api_http_error",
                status_code=e.response.status_code,
                keyword=keyword,
                error=str(e),
            )
            raise

        except httpx.TimeoutException as e:
            logger.error("coupang_api_timeout", keyword=keyword, error=str(e))
            raise

        except httpx.NetworkError as e:
            logger.error("coupang_api_network_error", keyword=keyword, error=str(e))
            raise

        except Exception as e:
            logger.error("coupang_api_unexpected_error", keyword=keyword, error=str(e))
            raise

    def _generate_auth_headers(
        self,
        method: str,
        path: str,
        datetime_str: str,
    ) -> Dict[str, str]:
        """Generate HMAC-SHA256 authentication headers for Coupang API.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: Request path with query parameters
            datetime_str: Current datetime in Coupang format (YYMMDDTHHMMSSZ)

        Returns:
            Dictionary of headers including Authorization
        """
        # Create message to sign
        message = datetime_str + method + path

        # Generate HMAC-SHA256 signature
        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        # Create authorization header
        authorization = f"CEA algorithm=HmacSHA256, access-key={self.access_key}, signed-date={datetime_str}, signature={signature}"

        return {
            "Authorization": authorization,
            "Content-Type": "application/json;charset=UTF-8",
        }

    @staticmethod
    def _build_query_string(params: Dict[str, Any]) -> str:
        """Build query string from parameters.

        Args:
            params: Dictionary of query parameters

        Returns:
            Query string starting with '?'
        """
        if not params:
            return ""

        query_parts = []
        for key, value in sorted(params.items()):  # Sort for consistent signature
            query_parts.append(f"{key}={value}")

        return "?" + "&".join(query_parts)

    def _normalize_item(
        self, item: Dict[str, Any], category_hint: Optional[str] = None
    ) -> Optional[NormalizedDeal]:
        """Convert Coupang API item to NormalizedDeal.

        Args:
            item: Raw item from Coupang API response
            category_hint: Optional category hint from search keyword

        Returns:
            NormalizedDeal object or None if item is invalid
        """
        # Extract and clean data
        title = item.get("productName", "")
        if not title:
            logger.warning("item_missing_title", item=item)
            return None

        # Parse prices
        product_price = PriceNormalizer.clean_price_string(
            str(item.get("productPrice", "0"))
        )

        if not product_price or product_price <= 0:
            logger.debug("item_invalid_price", title=title, price=item.get("productPrice"))
            return None

        # Determine original price and discount
        # Coupang doesn't always provide original price in search results
        original_price = None
        discount_percentage = None

        # Auto-classify category
        classified_category = CategoryClassifier.classify(
            title, shop_category=item.get("categoryName")
        )
        # Use category hint from search keyword if classification fails
        if not classified_category:
            classified_category = category_hint

        # Create product
        product = NormalizedProduct(
            external_id=str(item.get("productId", "")),
            title=title,
            current_price=product_price,
            original_price=original_price,
            currency="KRW",
            product_url=item.get("productUrl", ""),
            image_url=item.get("productImage", ""),
            brand=None,  # Not provided in search API
            category_hint=classified_category,
            description=None,
            metadata={
                "category_name": item.get("categoryName", ""),
                "is_rocket": item.get("isRocket", False),
                "is_fresh": item.get("isFresh", False),
                "free_shipping": item.get("freeShipping", False),
            },
        )

        # Determine deal type
        deal_type = "price_drop"
        if item.get("isRocket"):
            # Rocket items might be flash sales
            deal_type = "flash_sale"

        # Create deal
        deal = NormalizedDeal(
            product=product,
            deal_price=product_price,
            title=title,
            deal_url=item.get("productUrl", ""),
            original_price=original_price,
            discount_percentage=discount_percentage,
            deal_type=deal_type,
            description=None,
            image_url=item.get("productImage", ""),
            starts_at=None,
            expires_at=None,
            metadata={
                "category_name": item.get("categoryName", ""),
                "is_rocket": item.get("isRocket", False),
                "is_fresh": item.get("isFresh", False),
                "free_shipping": item.get("freeShipping", False),
            },
        )

        return deal

    async def cleanup(self) -> None:
        """Clean up resources. No persistent resources to clean."""
        pass
