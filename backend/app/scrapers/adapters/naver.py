"""Naver Shopping API adapter.

Fetches deals from Naver Shopping using the Naver Search API.
Documentation: https://developers.naver.com/docs/serviceapi/search/shopping/shopping.md
"""

import re
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


class NaverShoppingAdapter(BaseAPIAdapter):
    """Naver Shopping API adapter for fetching product deals.

    Uses the Naver Search Shopping API to find deals across multiple categories.
    Requires NAVER_CLIENT_ID and NAVER_CLIENT_SECRET in environment variables.
    """

    shop_slug = "naver"
    shop_name = "네이버쇼핑"
    adapter_type = "api"

    # API Configuration
    API_BASE_URL = "https://openapi.naver.com/v1/search/shop.json"
    API_DOMAIN = "openapi.naver.com"

    # Category-specific search keywords.
    # Each list has broader terms first (more results) and specific ones after.
    # Naver Shopping API works well with Korean product names + deal terms.
    CATEGORY_KEYWORDS = {
        "pc-hardware": [
            "그래픽카드 할인",
            "SSD 특가",
            "CPU 할인",
            "RAM 특가",
            "메인보드 할인",
        ],
        "laptop-mobile": [
            "노트북 할인",
            "스마트폰 특가",
            "태블릿 할인",
            "갤럭시 특가",
            "아이폰 할인",
        ],
        "electronics-tv": [
            "TV 할인",
            "모니터 특가",
            "세탁기 할인",
            "냉장고 특가",
            "에어컨 할인",
        ],
        "games-software": [
            "게임 할인",
            "PS5 특가",
            "닌텐도 스위치 할인",
            "Xbox 특가",
        ],
        "gift-cards": [
            "상품권 할인",
            "기프트카드 특가",
            "문화상품권 할인",
        ],
        "living-food": [
            "식품 할인",
            "생활용품 특가",
            "건강식품 할인",
            "다이어트 특가",
        ],
    }

    # General deal keywords searched regardless of category.
    # These cast a wider net to capture cross-category hot deals.
    GENERAL_KEYWORDS = [
        "오늘의특가",
        "타임특가",
        "반값특가",
        "핫딜",
        "특가세일",
    ]

    def __init__(self):
        """Initialize Naver Shopping adapter."""
        super().__init__()
        self.client_id = settings.NAVER_CLIENT_ID
        self.client_secret = settings.NAVER_CLIENT_SECRET

        if not self.client_id or not self.client_secret:
            logger.warning(
                "naver_credentials_missing",
                message="NAVER_CLIENT_ID or NAVER_CLIENT_SECRET not set",
            )

        # Initialize rate limiter if not injected
        if not self.rate_limiter:
            self.rate_limiter = DomainRateLimiter()
            # Naver API limit: 25,000 calls/day = ~17 calls/minute
            # Set conservative limit to avoid hitting daily quota too fast
            self.rate_limiter.set_custom_limit(self.API_DOMAIN, 15)

        # HTTP client will be created per-request to avoid lifecycle issues
        self._timeout = 30.0

    async def fetch_deals(self, category: Optional[str] = None) -> List[NormalizedDeal]:
        """Fetch current deals from Naver Shopping.

        Args:
            category: Optional category filter (e.g., "pc-hardware")
                     If None, fetches deals from all categories.

        Returns:
            List of NormalizedDeal objects. Returns empty list if credentials
            are missing (logs warning instead of raising).
        """
        if not self.client_id or not self.client_secret:
            logger.warning(
                "naver_fetch_skipped",
                message=(
                    "NAVER_CLIENT_ID or NAVER_CLIENT_SECRET not configured. "
                    "Set these environment variables on Render to enable Naver scraping."
                ),
            )
            return []

        deals: List[NormalizedDeal] = []
        seen_product_ids = set()  # For deduplication

        # Determine which category keywords to search
        if category and category in self.CATEGORY_KEYWORDS:
            keyword_groups = {category: self.CATEGORY_KEYWORDS[category]}
            # When filtering by category, skip general keywords
            general_keywords = []
        elif category:
            logger.warning(
                "unknown_category",
                category=category,
                message="Category not found in keyword map, searching all categories",
            )
            keyword_groups = self.CATEGORY_KEYWORDS
            general_keywords = self.GENERAL_KEYWORDS
        else:
            keyword_groups = self.CATEGORY_KEYWORDS
            general_keywords = self.GENERAL_KEYWORDS

        async def _search_and_collect(
            keyword: str,
            cat_slug: str,
            sort: str = "sim",
        ) -> None:
            """Search a keyword and add results to deals list."""
            try:
                logger.info(
                    "searching_naver",
                    category=cat_slug,
                    keyword=keyword,
                )

                results = await self._call_api(
                    query=keyword,
                    display=30,  # Get top 30 results per keyword
                    sort=sort,
                )

                for item in results.get("items", []):
                    product_id = item.get("productId")

                    # Skip items with no product ID (mall-level items)
                    if not product_id:
                        continue

                    # Skip if already processed (deduplication)
                    if product_id in seen_product_ids:
                        continue

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

        # Search category-specific keywords (sorted by relevance)
        for cat_slug, keywords in keyword_groups.items():
            for keyword in keywords:
                await _search_and_collect(keyword, cat_slug, sort="sim")

        # Search general hot-deal keywords (sorted by relevance)
        for keyword in general_keywords:
            await _search_and_collect(keyword, "general", sort="sim")

        logger.info(
            "naver_fetch_complete",
            total_deals=len(deals),
            unique_products=len(seen_product_ids),
            category=category,
        )

        return deals

    async def fetch_product_details(self, external_id: str) -> Optional[NormalizedProduct]:
        """Fetch detailed information for a specific product.

        Args:
            external_id: Naver product ID

        Returns:
            NormalizedProduct or None if not found
        """
        try:
            # Search by product ID
            results = await self._call_api(
                query=external_id,
                display=1,
            )

            items = results.get("items", [])
            if not items:
                logger.warning("product_not_found", product_id=external_id)
                return None

            item = items[0]

            # Create normalized product
            title = self._strip_html(item.get("title", ""))
            lprice = PriceNormalizer.clean_price_string(str(item.get("lprice", "0")))
            hprice = PriceNormalizer.clean_price_string(str(item.get("hprice", "0")))

            if not lprice or lprice <= 0:
                logger.warning(
                    "invalid_product_price",
                    product_id=external_id,
                    lprice=item.get("lprice"),
                )
                return None

            product = NormalizedProduct(
                external_id=str(item.get("productId", external_id)),
                title=title,
                current_price=lprice,
                original_price=hprice if hprice and hprice > lprice else None,
                currency="KRW",
                product_url=item.get("link", ""),
                image_url=item.get("image", ""),
                brand=item.get("brand", "") or item.get("maker", "") or None,
                category_hint=CategoryClassifier.classify(title),
                description=None,  # Naver API doesn't provide description
                metadata={
                    "mall_name": item.get("mallName", ""),
                    "product_type": item.get("productType", ""),
                    "category1": item.get("category1", ""),
                    "category2": item.get("category2", ""),
                    "category3": item.get("category3", ""),
                    "category4": item.get("category4", ""),
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
        """Check if Naver API is accessible and credentials are valid.

        Returns:
            True if healthy, False if credentials are missing or API is unreachable
        """
        if not self.client_id or not self.client_secret:
            logger.warning(
                "naver_health_check_skipped",
                message="Credentials not configured, marking as unhealthy",
            )
            return False

        try:
            # Make a simple API call with a generic search term
            await self._call_api(query="특가", display=1)
            logger.info("naver_health_check_passed")
            return True
        except Exception as e:
            logger.error("naver_health_check_failed", error=str(e))
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    )
    async def _call_api(
        self,
        query: str,
        display: int = 30,
        start: int = 1,
        sort: str = "sim",
    ) -> Dict[str, Any]:
        """Make a call to the Naver Shopping API with retry logic.

        Args:
            query: Search query string
            display: Number of results to return (max 100)
            start: Starting position (1-based index)
            sort: Sort order (sim=relevance, date=newest, asc=price asc, dsc=price desc)

        Returns:
            API response as dictionary

        Raises:
            httpx.HTTPStatusError: If API returns error status
            httpx.TimeoutException: If request times out
            httpx.NetworkError: If network error occurs
        """
        # Rate limiting
        await self.rate_limiter.acquire(self.API_DOMAIN)

        # Build request
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
        }

        params = {
            "query": query,
            "display": min(display, 100),  # API max is 100
            "start": start,
            "sort": sort,
        }

        logger.debug(
            "naver_api_call",
            query=query,
            display=params["display"],
            sort=sort,
        )

        # Make request using context manager for proper cleanup
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    self.API_BASE_URL,
                    headers=headers,
                    params=params,
                )

                # Handle rate limiting
                if response.status_code == 429:
                    logger.warning("naver_rate_limit_hit", query=query)
                    raise httpx.HTTPStatusError(
                        "Rate limit exceeded",
                        request=response.request,
                        response=response,
                    )

                # Raise for other HTTP errors
                response.raise_for_status()

                data = response.json()
                logger.debug(
                    "naver_api_success",
                    query=query,
                    total_results=data.get("total", 0),
                    returned_items=len(data.get("items", [])),
                )

                return data

        except httpx.HTTPStatusError as e:
            logger.error(
                "naver_api_http_error",
                status_code=e.response.status_code,
                query=query,
                error=str(e),
            )
            raise

        except httpx.TimeoutException as e:
            logger.error("naver_api_timeout", query=query, error=str(e))
            raise

        except httpx.NetworkError as e:
            logger.error("naver_api_network_error", query=query, error=str(e))
            raise

        except Exception as e:
            logger.error("naver_api_unexpected_error", query=query, error=str(e))
            raise

    def _normalize_item(
        self, item: Dict[str, Any], category_hint: Optional[str] = None
    ) -> Optional[NormalizedDeal]:
        """Convert Naver API item to NormalizedDeal.

        Args:
            item: Raw item from Naver API response
            category_hint: Optional category hint from search keyword

        Returns:
            NormalizedDeal object or None if item is invalid
        """
        # Extract and clean data
        title = self._strip_html(item.get("title", ""))
        if not title:
            logger.warning("item_missing_title", item=item)
            return None

        # Parse prices (Naver returns prices as strings)
        lprice = PriceNormalizer.clean_price_string(str(item.get("lprice", "0")))
        hprice = PriceNormalizer.clean_price_string(str(item.get("hprice", "0")))

        if not lprice or lprice <= 0:
            logger.debug("item_invalid_price", title=title, lprice=item.get("lprice"))
            return None

        # Determine original price and discount
        original_price = None
        discount_percentage = None

        if hprice and hprice > lprice:
            original_price = hprice
            discount_percentage = self._calculate_discount_percentage(hprice, lprice)

        # Determine deal type
        deal_type = "price_drop"
        if discount_percentage and discount_percentage >= 30:
            deal_type = "flash_sale"
        elif discount_percentage and discount_percentage >= 10:
            deal_type = "price_drop"
        else:
            # Even without explicit discount, it's still a deal from search
            deal_type = "price_drop"

        # Auto-classify category using title keywords first,
        # then fall back to the search keyword's category hint.
        # Exclude "general" as it's not a real DB category slug.
        classified_category = CategoryClassifier.classify(
            title, shop_category=item.get("category1")
        )
        if not classified_category and category_hint and category_hint != "general":
            classified_category = category_hint

        # Create product
        product = NormalizedProduct(
            external_id=str(item.get("productId", "")),
            title=title,
            current_price=lprice,
            original_price=original_price,
            currency="KRW",
            product_url=item.get("link", ""),
            image_url=item.get("image", ""),
            brand=item.get("brand", "") or item.get("maker", "") or None,
            category_hint=classified_category,
            description=None,
            metadata={
                "mall_name": item.get("mallName", ""),
                "product_type": item.get("productType", ""),
                "category1": item.get("category1", ""),
                "category2": item.get("category2", ""),
                "category3": item.get("category3", ""),
                "category4": item.get("category4", ""),
            },
        )

        # Create deal
        deal = NormalizedDeal(
            product=product,
            deal_price=lprice,
            title=title,
            deal_url=item.get("link", ""),
            original_price=original_price,
            discount_percentage=discount_percentage,
            deal_type=deal_type,
            description=None,
            image_url=item.get("image", ""),
            starts_at=None,
            expires_at=None,
            metadata={
                "mall_name": item.get("mallName", ""),
                "product_type": item.get("productType", ""),
                "brand": item.get("brand", ""),
                "maker": item.get("maker", ""),
                "naver_category": f"{item.get('category1', '')} > {item.get('category2', '')}".strip(
                    " >"
                ),
            },
        )

        return deal

    @staticmethod
    def _strip_html(text: str) -> str:
        """Remove HTML tags from text.

        Naver API returns titles with <b> tags for search term highlighting.

        Args:
            text: Text with potential HTML tags

        Returns:
            Cleaned text without HTML tags
        """
        if not text:
            return ""

        # Remove HTML tags
        cleaned = re.sub(r"<[^>]+>", "", text)

        # Decode HTML entities
        cleaned = cleaned.replace("&lt;", "<")
        cleaned = cleaned.replace("&gt;", ">")
        cleaned = cleaned.replace("&amp;", "&")
        cleaned = cleaned.replace("&quot;", '"')
        cleaned = cleaned.replace("&#39;", "'")

        return cleaned.strip()

    async def cleanup(self) -> None:
        """Clean up resources. No persistent resources to clean."""
        pass
