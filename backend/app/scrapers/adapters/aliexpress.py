"""AliExpress Affiliate API adapter.

Fetches deals from AliExpress using the AliExpress Affiliate API.
Documentation: https://developers.aliexpress.com/en/doc.htm?docId=108976&docType=1
"""

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


class AliExpressAdapter(BaseAPIAdapter):
    """AliExpress Affiliate API adapter for fetching product deals.

    Uses the AliExpress Affiliate API to find deals across multiple categories.
    Requires ALIEXPRESS_APP_KEY and ALIEXPRESS_APP_SECRET in environment variables.
    """

    shop_slug = "aliexpress"
    shop_name = "알리익스프레스"
    adapter_type = "api"

    # API Configuration
    API_BASE_URL = "https://api-sg.aliexpress.com/sync"
    API_DOMAIN = "api-sg.aliexpress.com"
    API_METHOD = "aliexpress.affiliate.product.query"

    # Category-specific search keywords (Korean for product titles)
    CATEGORY_KEYWORDS = {
        "pc-hardware": [
            "노트북",
            "SSD",
            "그래픽카드",
            "RAM",
            "키보드 기계식",
        ],
        "laptop-mobile": [
            "노트북",
            "태블릿",
            "스마트워치",
        ],
        "electronics-tv": [
            "이어폰",
            "헤드폰",
            "스마트워치",
            "로봇청소기",
        ],
        "games-software": [
            "게임패드",
            "게임 컨트롤러",
        ],
        "living-food": [
            "보조배터리",
            "USB 케이블",
            "스마트폰 케이스",
        ],
    }

    def __init__(self):
        """Initialize AliExpress Affiliate adapter."""
        super().__init__()
        self.app_key = settings.ALIEXPRESS_APP_KEY
        self.app_secret = settings.ALIEXPRESS_APP_SECRET

        if not self.app_key or not self.app_secret:
            logger.warning(
                "aliexpress_credentials_missing",
                message="ALIEXPRESS_APP_KEY or ALIEXPRESS_APP_SECRET not set",
            )

        # Initialize rate limiter if not injected
        if not self.rate_limiter:
            self.rate_limiter = DomainRateLimiter()
            # Conservative limit: ~5,000 requests per day = ~3.5 req/min
            # Set to 5 req/min to be safe
            self.rate_limiter.set_custom_limit(self.API_DOMAIN, 5)

        # HTTP client will be created per-request to avoid lifecycle issues
        self._timeout = 30.0

    async def fetch_deals(self, category: Optional[str] = None) -> List[NormalizedDeal]:
        """Fetch current deals from AliExpress Affiliate API.

        Args:
            category: Optional category filter (e.g., "pc-hardware")
                     If None, fetches deals from all categories.

        Returns:
            List of NormalizedDeal objects

        Raises:
            Exception: If API credentials are missing or API call fails
        """
        if not self.app_key or not self.app_secret:
            raise ValueError(
                "AliExpress API credentials not configured. "
                "Set ALIEXPRESS_APP_KEY and ALIEXPRESS_APP_SECRET in .env file."
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
                        "searching_aliexpress",
                        category=cat_slug,
                        keyword=keyword,
                    )

                    # Fetch results for this keyword
                    results = await self._call_api(
                        keywords=keyword,
                        page_size=30,  # Get top 30 results per keyword
                        page_no=1,
                        sort="SALE_PRICE_ASC",  # Sort by price ascending
                    )

                    # Navigate nested response structure
                    products = (
                        results.get("aliexpress_affiliate_product_query_response", {})
                        .get("resp_result", {})
                        .get("result", {})
                        .get("products", {})
                        .get("product", [])
                    )

                    # Normalize each item
                    for item in products:
                        product_id = item.get("product_id")

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
            "aliexpress_fetch_complete",
            total_deals=len(deals),
            unique_products=len(seen_product_ids),
            category=category,
        )

        return deals

    async def fetch_product_details(self, external_id: str) -> Optional[NormalizedProduct]:
        """Fetch detailed information for a specific product.

        Args:
            external_id: AliExpress product ID

        Returns:
            NormalizedProduct or None if not found
        """
        try:
            # Search by product ID
            results = await self._call_api(
                keywords=external_id,
                page_size=1,
                page_no=1,
            )

            # Navigate nested response structure
            products = (
                results.get("aliexpress_affiliate_product_query_response", {})
                .get("resp_result", {})
                .get("result", {})
                .get("products", {})
                .get("product", [])
            )

            if not products:
                logger.warning("product_not_found", product_id=external_id)
                return None

            item = products[0]

            # Create normalized product
            title = item.get("product_title", "")
            sale_price = PriceNormalizer.clean_price_string(
                str(item.get("target_sale_price", "0"))
            )
            original_price = PriceNormalizer.clean_price_string(
                str(item.get("target_original_price", "0"))
            )

            if not sale_price or sale_price <= 0:
                logger.warning(
                    "invalid_product_price",
                    product_id=external_id,
                    sale_price=item.get("target_sale_price"),
                )
                return None

            product = NormalizedProduct(
                external_id=str(item.get("product_id", external_id)),
                title=title,
                current_price=sale_price,
                original_price=original_price if original_price and original_price > sale_price else None,
                currency="KRW",
                product_url=item.get("product_detail_url", ""),
                image_url=item.get("product_main_image_url", ""),
                brand=None,  # Not provided in AliExpress API
                category_hint=CategoryClassifier.classify(title),
                description=None,  # Not provided in search API
                metadata={
                    "discount": item.get("discount", ""),
                    "evaluate_rate": item.get("evaluate_rate", ""),
                    "shop_url": item.get("shop_url", ""),
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
        """Check if AliExpress API is accessible and credentials are valid.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Make a simple API call with a generic search term
            await self._call_api(keywords="test", page_size=1, page_no=1)
            logger.info("aliexpress_health_check_passed")
            return True
        except Exception as e:
            logger.error("aliexpress_health_check_failed", error=str(e))
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    )
    async def _call_api(
        self,
        keywords: str,
        page_size: int = 30,
        page_no: int = 1,
        sort: str = "SALE_PRICE_ASC",
        min_sale_price: Optional[str] = None,
        max_sale_price: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Make a call to the AliExpress Affiliate API with retry logic.

        Args:
            keywords: Search query string
            page_size: Number of results per page (max 50)
            page_no: Page number (1-based)
            sort: Sort order (SALE_PRICE_ASC, SALE_PRICE_DESC, etc.)
            min_sale_price: Minimum sale price filter
            max_sale_price: Maximum sale price filter

        Returns:
            API response as dictionary

        Raises:
            httpx.HTTPStatusError: If API returns error status
            httpx.TimeoutException: If request times out
            httpx.NetworkError: If network error occurs
        """
        # Rate limiting
        await self.rate_limiter.acquire(self.API_DOMAIN)

        # Build request parameters
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        params = {
            "app_key": self.app_key,
            "method": self.API_METHOD,
            "sign_method": "md5",
            "timestamp": timestamp,
            "target_currency": "KRW",
            "target_language": "KO",
            "keywords": keywords,
            "page_no": str(page_no),
            "page_size": str(min(page_size, 50)),  # API max is 50
            "sort": sort,
        }

        # Add optional parameters
        if min_sale_price:
            params["min_sale_price"] = min_sale_price
        if max_sale_price:
            params["max_sale_price"] = max_sale_price

        # Generate signature
        params["sign"] = self._generate_signature(params)

        logger.debug(
            "aliexpress_api_call",
            keywords=keywords,
            page_size=params["page_size"],
            sort=sort,
        )

        # Make request using context manager for proper cleanup
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    self.API_BASE_URL,
                    params=params,
                )

                # Handle rate limiting
                if response.status_code == 429:
                    logger.warning("aliexpress_rate_limit_hit", keywords=keywords)
                    raise httpx.HTTPStatusError(
                        "Rate limit exceeded",
                        request=response.request,
                        response=response,
                    )

                # Raise for other HTTP errors
                response.raise_for_status()

                data = response.json()

                # Check for API-level errors
                resp_result = (
                    data.get("aliexpress_affiliate_product_query_response", {})
                    .get("resp_result", {})
                )

                if resp_result.get("resp_code") != 200:
                    error_msg = resp_result.get("resp_msg", "Unknown error")
                    logger.error(
                        "aliexpress_api_error",
                        error_code=resp_result.get("resp_code"),
                        error_msg=error_msg,
                        keywords=keywords,
                    )
                    raise Exception(f"AliExpress API error: {error_msg}")

                products_count = len(
                    resp_result.get("result", {})
                    .get("products", {})
                    .get("product", [])
                )

                logger.debug(
                    "aliexpress_api_success",
                    keywords=keywords,
                    returned_items=products_count,
                )

                return data

        except httpx.HTTPStatusError as e:
            logger.error(
                "aliexpress_api_http_error",
                status_code=e.response.status_code,
                keywords=keywords,
                error=str(e),
            )
            raise

        except httpx.TimeoutException as e:
            logger.error("aliexpress_api_timeout", keywords=keywords, error=str(e))
            raise

        except httpx.NetworkError as e:
            logger.error("aliexpress_api_network_error", keywords=keywords, error=str(e))
            raise

        except Exception as e:
            logger.error("aliexpress_api_unexpected_error", keywords=keywords, error=str(e))
            raise

    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """Generate MD5 signature for AliExpress API request.

        Args:
            params: Dictionary of request parameters (without 'sign')

        Returns:
            Uppercase MD5 hex string signature
        """
        # Sort parameters by key alphabetically
        sorted_params = sorted(params.items())

        # Concatenate key+value pairs
        sign_string = self.app_secret
        for key, value in sorted_params:
            if key != "sign":  # Don't include sign in signature
                sign_string += f"{key}{value}"
        sign_string += self.app_secret

        # Generate MD5 hash and return uppercase
        signature = hashlib.md5(sign_string.encode("utf-8")).hexdigest().upper()

        return signature

    def _normalize_item(
        self, item: Dict[str, Any], category_hint: Optional[str] = None
    ) -> Optional[NormalizedDeal]:
        """Convert AliExpress API item to NormalizedDeal.

        Args:
            item: Raw item from AliExpress API response
            category_hint: Optional category hint from search keyword

        Returns:
            NormalizedDeal object or None if item is invalid
        """
        # Extract and clean data
        title = item.get("product_title", "")
        if not title:
            logger.warning("item_missing_title", item=item)
            return None

        # Parse prices (AliExpress returns in target currency - KRW)
        sale_price = PriceNormalizer.clean_price_string(
            str(item.get("target_sale_price", "0"))
        )
        original_price = PriceNormalizer.clean_price_string(
            str(item.get("target_original_price", "0"))
        )

        if not sale_price or sale_price <= 0:
            logger.debug("item_invalid_price", title=title, price=item.get("target_sale_price"))
            return None

        # Determine discount
        discount_percentage = None
        final_original_price = None

        if original_price and original_price > sale_price:
            final_original_price = original_price
            discount_percentage = self._calculate_discount_percentage(original_price, sale_price)
        else:
            # Try to parse discount string (e.g., "50%")
            discount_str = item.get("discount", "")
            if discount_str and isinstance(discount_str, str):
                try:
                    # Remove '%' and convert to decimal
                    discount_value = Decimal(discount_str.replace("%", "").strip())
                    if 0 < discount_value <= 100:
                        discount_percentage = discount_value
                except (ValueError, Exception):
                    pass

        # Determine deal type
        deal_type = "price_drop"
        if discount_percentage and discount_percentage >= 50:
            deal_type = "flash_sale"
        elif discount_percentage and discount_percentage >= 20:
            deal_type = "price_drop"

        # Auto-classify category
        classified_category = CategoryClassifier.classify(title)
        # Use category hint from search keyword if classification fails
        if not classified_category:
            classified_category = category_hint

        # Create product
        product = NormalizedProduct(
            external_id=str(item.get("product_id", "")),
            title=title,
            current_price=sale_price,
            original_price=final_original_price,
            currency="KRW",
            product_url=item.get("product_detail_url", ""),
            image_url=item.get("product_main_image_url", ""),
            brand=None,  # AliExpress API doesn't provide brand
            category_hint=classified_category,
            description=None,
            metadata={
                "discount": item.get("discount", ""),
                "evaluate_rate": item.get("evaluate_rate", ""),
                "shop_url": item.get("shop_url", ""),
                "original_price_value": str(item.get("original_price", "")),
                "sale_price_value": str(item.get("sale_price", "")),
            },
        )

        # Create deal
        deal = NormalizedDeal(
            product=product,
            deal_price=sale_price,
            title=title,
            deal_url=item.get("product_detail_url", ""),
            original_price=final_original_price,
            discount_percentage=discount_percentage,
            deal_type=deal_type,
            description=None,
            image_url=item.get("product_main_image_url", ""),
            starts_at=None,
            expires_at=None,
            metadata={
                "discount": item.get("discount", ""),
                "evaluate_rate": item.get("evaluate_rate", ""),
                "shop_url": item.get("shop_url", ""),
            },
        )

        return deal

    async def cleanup(self) -> None:
        """Clean up resources. No persistent resources to clean."""
        pass
