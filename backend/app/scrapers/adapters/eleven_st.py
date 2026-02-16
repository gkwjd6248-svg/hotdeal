"""11st Open API adapter.

Fetches deals from 11st using the 11st Open API.
Documentation: http://openapi.11st.co.kr/
"""

import re
import httpx
import xml.etree.ElementTree as ET
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


class ElevenStAdapter(BaseAPIAdapter):
    """11st Open API adapter for fetching product deals.

    Uses the 11st Open API to find deals across multiple categories.
    Requires ELEVEN_ST_API_KEY in environment variables.
    Note: 11st API returns XML, not JSON.
    """

    shop_slug = "11st"
    shop_name = "11번가"
    adapter_type = "api"

    # API Configuration
    API_BASE_URL = "http://openapi.11st.co.kr/openapi/OpenApiService.tmall"
    API_DOMAIN = "openapi.11st.co.kr"
    API_CODE = "ProductSearch"

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
        """Initialize 11st Open API adapter."""
        super().__init__()
        self.api_key = settings.ELEVEN_ST_API_KEY

        if not self.api_key:
            logger.warning(
                "eleven_st_credentials_missing",
                message="ELEVEN_ST_API_KEY not set",
            )

        # Initialize rate limiter if not injected
        if not self.rate_limiter:
            self.rate_limiter = DomainRateLimiter()
            # 11st API limit: ~1,000 calls/day = conservative 2 requests per minute
            self.rate_limiter.set_custom_limit(self.API_DOMAIN, 2)

        # HTTP client will be created per-request to avoid lifecycle issues
        self._timeout = 30.0

    async def fetch_deals(self, category: Optional[str] = None) -> List[NormalizedDeal]:
        """Fetch current deals from 11st Open API.

        Args:
            category: Optional category filter (e.g., "pc-hardware")
                     If None, fetches deals from all categories.

        Returns:
            List of NormalizedDeal objects

        Raises:
            Exception: If API credentials are missing or API call fails
        """
        if not self.api_key:
            raise ValueError(
                "11st API credentials not configured. "
                "Set ELEVEN_ST_API_KEY in .env file."
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
                        "searching_eleven_st",
                        category=cat_slug,
                        keyword=keyword,
                    )

                    # Fetch results for this keyword
                    results = await self._call_api(
                        keyword=keyword,
                        page_size=30,  # Get top 30 results per keyword
                        page_num=1,
                        sort_cd="SD",  # Sort by discount rate (special deals)
                    )

                    # Normalize each item
                    for item in results:
                        product_code = item.get("ProductCode")

                        # Skip if already processed (deduplication)
                        if product_code in seen_product_ids:
                            continue

                        # Normalize and add deal
                        try:
                            deal = self._normalize_item(item, category_hint=cat_slug)
                            if deal:
                                deals.append(deal)
                                seen_product_ids.add(product_code)
                        except Exception as e:
                            logger.error(
                                "normalization_failed",
                                product_code=product_code,
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
            "eleven_st_fetch_complete",
            total_deals=len(deals),
            unique_products=len(seen_product_ids),
            category=category,
        )

        return deals

    async def fetch_product_details(self, external_id: str) -> Optional[NormalizedProduct]:
        """Fetch detailed information for a specific product.

        Args:
            external_id: 11st product code

        Returns:
            NormalizedProduct or None if not found
        """
        try:
            # Search by product code
            results = await self._call_api(
                keyword=external_id,
                page_size=1,
                page_num=1,
            )

            if not results:
                logger.warning("product_not_found", product_code=external_id)
                return None

            item = results[0]

            # Create normalized product
            title = item.get("ProductName", "")
            sale_price = PriceNormalizer.clean_price_string(
                str(item.get("SalePrice", "0"))
            )
            product_price = PriceNormalizer.clean_price_string(
                str(item.get("ProductPrice", "0"))
            )

            if not sale_price or sale_price <= 0:
                logger.warning(
                    "invalid_product_price",
                    product_code=external_id,
                    sale_price=item.get("SalePrice"),
                )
                return None

            product = NormalizedProduct(
                external_id=str(item.get("ProductCode", external_id)),
                title=title,
                current_price=sale_price,
                original_price=product_price if product_price and product_price > sale_price else None,
                currency="KRW",
                product_url=item.get("DetailPageUrl", ""),
                image_url=item.get("ProductImage", ""),
                brand=None,  # Not always provided
                category_hint=CategoryClassifier.classify(title),
                description=None,  # Not provided in search API
                metadata={
                    "discount": item.get("Discount", "0"),
                    "delivery_fee": item.get("DeliveryFee", "0"),
                },
            )

            return product

        except Exception as e:
            logger.error(
                "fetch_product_failed",
                product_code=external_id,
                error=str(e),
            )
            return None

    async def health_check(self) -> bool:
        """Check if 11st API is accessible and credentials are valid.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Make a simple API call with a generic search term
            await self._call_api(keyword="테스트", page_size=1, page_num=1)
            logger.info("eleven_st_health_check_passed")
            return True
        except Exception as e:
            logger.error("eleven_st_health_check_failed", error=str(e))
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    )
    async def _call_api(
        self,
        keyword: str,
        page_size: int = 30,
        page_num: int = 1,
        sort_cd: str = "SD",
    ) -> List[Dict[str, Any]]:
        """Make a call to the 11st Open API with retry logic.

        Args:
            keyword: Search query string
            page_size: Number of results to return per page (max 200)
            page_num: Page number (1-based)
            sort_cd: Sort code (SD=discount, PA=price asc, PD=price desc, CP=popular)

        Returns:
            List of product dictionaries parsed from XML

        Raises:
            httpx.HTTPStatusError: If API returns error status
            httpx.TimeoutException: If request times out
            httpx.NetworkError: If network error occurs
        """
        # Rate limiting
        await self.rate_limiter.acquire(self.API_DOMAIN)

        # Build request parameters
        params = {
            "key": self.api_key,
            "apiCode": self.API_CODE,
            "keyword": keyword,
            "pageSize": min(page_size, 200),  # API max is 200
            "pageNum": page_num,
            "sortCd": sort_cd,
        }

        logger.debug(
            "eleven_st_api_call",
            keyword=keyword,
            page_size=params["pageSize"],
            sort_cd=sort_cd,
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
                    logger.warning("eleven_st_rate_limit_hit", keyword=keyword)
                    raise httpx.HTTPStatusError(
                        "Rate limit exceeded",
                        request=response.request,
                        response=response,
                    )

                # Raise for other HTTP errors
                response.raise_for_status()

                # Parse XML response
                products = self._parse_xml_response(response.text)

                logger.debug(
                    "eleven_st_api_success",
                    keyword=keyword,
                    returned_items=len(products),
                )

                return products

        except httpx.HTTPStatusError as e:
            logger.error(
                "eleven_st_api_http_error",
                status_code=e.response.status_code,
                keyword=keyword,
                error=str(e),
            )
            raise

        except httpx.TimeoutException as e:
            logger.error("eleven_st_api_timeout", keyword=keyword, error=str(e))
            raise

        except httpx.NetworkError as e:
            logger.error("eleven_st_api_network_error", keyword=keyword, error=str(e))
            raise

        except ET.ParseError as e:
            logger.error("eleven_st_xml_parse_error", keyword=keyword, error=str(e))
            raise

        except Exception as e:
            logger.error("eleven_st_api_unexpected_error", keyword=keyword, error=str(e))
            raise

    def _parse_xml_response(self, xml_string: str) -> List[Dict[str, Any]]:
        """Parse XML response from 11st API.

        Args:
            xml_string: XML response as string

        Returns:
            List of product dictionaries

        Raises:
            ET.ParseError: If XML is malformed
        """
        try:
            # Parse XML
            root = ET.fromstring(xml_string)

            # Find all Product elements
            products = []
            for product_elem in root.findall(".//Product"):
                product_data = {}

                # Extract all child elements
                for child in product_elem:
                    # Get text content, stripping whitespace
                    text = child.text.strip() if child.text else ""
                    product_data[child.tag] = text

                products.append(product_data)

            return products

        except ET.ParseError as e:
            logger.error(
                "xml_parse_failed",
                error=str(e),
                xml_preview=xml_string[:500],  # Log first 500 chars for debugging
            )
            raise

    def _normalize_item(
        self, item: Dict[str, Any], category_hint: Optional[str] = None
    ) -> Optional[NormalizedDeal]:
        """Convert 11st API item to NormalizedDeal.

        Args:
            item: Raw item from 11st API response (parsed from XML)
            category_hint: Optional category hint from search keyword

        Returns:
            NormalizedDeal object or None if item is invalid
        """
        # Extract and clean data
        title = item.get("ProductName", "")
        if not title:
            logger.warning("item_missing_title", item=item)
            return None

        # Parse prices (11st returns prices as strings)
        sale_price = PriceNormalizer.clean_price_string(
            str(item.get("SalePrice", "0"))
        )
        product_price = PriceNormalizer.clean_price_string(
            str(item.get("ProductPrice", "0"))
        )

        if not sale_price or sale_price <= 0:
            logger.debug("item_invalid_price", title=title, sale_price=item.get("SalePrice"))
            return None

        # Determine original price and discount
        original_price = None
        discount_percentage = None

        if product_price and product_price > sale_price:
            original_price = product_price
            discount_percentage = self._calculate_discount_percentage(product_price, sale_price)
        else:
            # Try to parse discount percentage from API
            discount_str = item.get("Discount", "0")
            try:
                discount_val = PriceNormalizer.clean_price_string(discount_str)
                if discount_val and discount_val > 0:
                    discount_percentage = discount_val
                    # Calculate original price if we have discount percentage
                    if sale_price > 0 and 0 < discount_percentage < 100:
                        original_price = sale_price / (1 - discount_percentage / 100)
            except Exception:
                pass

        # Determine deal type
        deal_type = "price_drop"
        if discount_percentage and discount_percentage >= 30:
            deal_type = "flash_sale"
        elif discount_percentage and discount_percentage >= 10:
            deal_type = "price_drop"

        # Auto-classify category
        classified_category = CategoryClassifier.classify(title)
        # Use category hint from search keyword if classification fails
        if not classified_category:
            classified_category = category_hint

        # Create product
        product = NormalizedProduct(
            external_id=str(item.get("ProductCode", "")),
            title=title,
            current_price=sale_price,
            original_price=original_price,
            currency="KRW",
            product_url=item.get("DetailPageUrl", ""),
            image_url=item.get("ProductImage", ""),
            brand=None,  # Not always provided
            category_hint=classified_category,
            description=None,
            metadata={
                "discount": item.get("Discount", "0"),
                "delivery_fee": item.get("DeliveryFee", "0"),
            },
        )

        # Create deal
        deal = NormalizedDeal(
            product=product,
            deal_price=sale_price,
            title=title,
            deal_url=item.get("DetailPageUrl", ""),
            original_price=original_price,
            discount_percentage=discount_percentage,
            deal_type=deal_type,
            description=None,
            image_url=item.get("ProductImage", ""),
            starts_at=None,
            expires_at=None,
            metadata={
                "discount": item.get("Discount", "0"),
                "delivery_fee": item.get("DeliveryFee", "0"),
            },
        )

        return deal

    async def cleanup(self) -> None:
        """Clean up resources. No persistent resources to clean."""
        pass
