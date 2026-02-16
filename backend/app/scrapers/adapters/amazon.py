"""Amazon PA-API 5.0 adapter.

Fetches deals from Amazon using the Product Advertising API 5.0.
Documentation: https://webservices.amazon.com/paapi5/documentation/
"""

import json
import hmac
import hashlib
import httpx
from decimal import Decimal
from typing import List, Optional, Dict, Any
from datetime import datetime
from urllib.parse import urlparse

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


class AmazonAdapter(BaseAPIAdapter):
    """Amazon Product Advertising API 5.0 adapter for fetching product deals.

    Uses the Amazon PA-API 5.0 to find deals across multiple categories.
    Requires AMAZON_ACCESS_KEY, AMAZON_SECRET_KEY, and AMAZON_PARTNER_TAG in environment variables.
    Implements AWS Signature Version 4 authentication.
    """

    shop_slug = "amazon"
    shop_name = "아마존"
    adapter_type = "api"

    # API Configuration
    API_BASE_URL = "https://webservices.amazon.com/paapi5/searchitems"
    API_DOMAIN = "webservices.amazon.com"
    API_REGION = "us-east-1"
    API_SERVICE = "ProductAdvertisingAPI"
    API_MARKETPLACE = "www.amazon.com"

    # Category-specific search keywords (English for Amazon.com)
    CATEGORY_KEYWORDS = {
        "pc-hardware": [
            "gaming PC deal",
            "SSD deal",
            "graphics card deal",
            "CPU discount",
            "RAM memory deal",
        ],
        "laptop-mobile": [
            "laptop deal",
            "tablet deal",
            "smartphone discount",
            "MacBook sale",
        ],
        "electronics-tv": [
            "TV deal",
            "headphones discount",
            "smart home deal",
            "monitor sale",
            "speaker discount",
        ],
        "games-software": [
            "PS5 game deal",
            "Nintendo Switch deal",
            "Xbox game discount",
            "video game sale",
        ],
        "gift-cards": [
            "gift card",
            "Amazon gift card",
        ],
        "living-food": [
            "grocery deal",
            "household essentials",
            "health supplements discount",
        ],
    }

    def __init__(self):
        """Initialize Amazon PA-API adapter."""
        super().__init__()
        self.access_key = settings.AMAZON_ACCESS_KEY
        self.secret_key = settings.AMAZON_SECRET_KEY
        self.partner_tag = settings.AMAZON_PARTNER_TAG

        if not self.access_key or not self.secret_key or not self.partner_tag:
            logger.warning(
                "amazon_credentials_missing",
                message="AMAZON_ACCESS_KEY, AMAZON_SECRET_KEY, or AMAZON_PARTNER_TAG not set",
            )

        # Initialize rate limiter if not injected
        if not self.rate_limiter:
            self.rate_limiter = DomainRateLimiter()
            # Amazon PA-API limit: 1 req/sec = 60 RPM, set conservative to 10 RPM
            self.rate_limiter.set_custom_limit(self.API_DOMAIN, 10)

        # HTTP client will be created per-request to avoid lifecycle issues
        self._timeout = 30.0

    async def fetch_deals(self, category: Optional[str] = None) -> List[NormalizedDeal]:
        """Fetch current deals from Amazon PA-API.

        Args:
            category: Optional category filter (e.g., "pc-hardware")
                     If None, fetches deals from all categories.

        Returns:
            List of NormalizedDeal objects

        Raises:
            Exception: If API credentials are missing or API call fails
        """
        if not self.access_key or not self.secret_key or not self.partner_tag:
            raise ValueError(
                "Amazon API credentials not configured. "
                "Set AMAZON_ACCESS_KEY, AMAZON_SECRET_KEY, and AMAZON_PARTNER_TAG in .env file."
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
                        "searching_amazon",
                        category=cat_slug,
                        keyword=keyword,
                    )

                    # Fetch results for this keyword
                    results = await self._call_api(keyword=keyword, item_count=10)

                    # Normalize each item
                    for item in results.get("SearchResult", {}).get("Items", []):
                        asin = item.get("ASIN")

                        # Skip if already processed (deduplication)
                        if asin in seen_product_ids:
                            continue

                        # Normalize and add deal
                        try:
                            deal = self._normalize_item(item, category_hint=cat_slug)
                            if deal:
                                deals.append(deal)
                                seen_product_ids.add(asin)
                        except Exception as e:
                            logger.error(
                                "normalization_failed",
                                asin=asin,
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
            "amazon_fetch_complete",
            total_deals=len(deals),
            unique_products=len(seen_product_ids),
            category=category,
        )

        return deals

    async def fetch_product_details(self, external_id: str) -> Optional[NormalizedProduct]:
        """Fetch detailed information for a specific product by ASIN.

        Args:
            external_id: Amazon ASIN

        Returns:
            NormalizedProduct or None if not found
        """
        try:
            # Search by ASIN (use GetItems endpoint would be better, but using search for consistency)
            results = await self._call_api(keyword=external_id, item_count=1)

            items = results.get("SearchResult", {}).get("Items", [])
            if not items:
                logger.warning("product_not_found", asin=external_id)
                return None

            item = items[0]

            # Create normalized product
            title = item.get("ItemInfo", {}).get("Title", {}).get("DisplayValue", "")

            # Extract price from Offers
            offers = item.get("Offers", {}).get("Listings", [])
            if not offers:
                logger.warning("no_offers_found", asin=external_id)
                return None

            offer = offers[0]
            price_data = offer.get("Price", {})

            # Price is in USD cents
            price_amount = price_data.get("Amount", 0)
            if not price_amount or price_amount <= 0:
                logger.warning(
                    "invalid_product_price",
                    asin=external_id,
                    price_amount=price_amount,
                )
                return None

            # Convert USD cents to KRW
            price_usd = Decimal(str(price_amount))
            current_price = PriceNormalizer.to_krw(price_usd, "USD")

            # Get original price if available
            original_price = None
            saved_amount = offer.get("SavingBasis", {}).get("Amount") or offer.get("Price", {}).get("Savings", {}).get("Amount")
            if saved_amount:
                original_price_usd = Decimal(str(saved_amount))
                original_price = PriceNormalizer.to_krw(original_price_usd, "USD")

            # Extract image URL
            image_url = ""
            images = item.get("Images", {}).get("Primary", {})
            if images:
                large_image = images.get("Large", {})
                image_url = large_image.get("URL", "")

            product = NormalizedProduct(
                external_id=item.get("ASIN", external_id),
                title=title,
                current_price=current_price,
                original_price=original_price,
                currency="KRW",
                product_url=item.get("DetailPageURL", ""),
                image_url=image_url,
                brand=item.get("ItemInfo", {}).get("ByLineInfo", {}).get("Brand", {}).get("DisplayValue"),
                category_hint=CategoryClassifier.classify(title),
                description=None,  # PA-API 5.0 search doesn't provide description
                metadata={
                    "asin": item.get("ASIN", ""),
                    "parent_asin": item.get("ParentASIN", ""),
                },
            )

            return product

        except Exception as e:
            logger.error(
                "fetch_product_failed",
                asin=external_id,
                error=str(e),
            )
            return None

    async def health_check(self) -> bool:
        """Check if Amazon PA-API is accessible and credentials are valid.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Make a simple API call with a generic search term
            await self._call_api(keyword="laptop", item_count=1)
            logger.info("amazon_health_check_passed")
            return True
        except Exception as e:
            logger.error("amazon_health_check_failed", error=str(e))
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    )
    async def _call_api(
        self,
        keyword: str,
        item_count: int = 10,
        search_index: str = "All",
    ) -> Dict[str, Any]:
        """Make a call to the Amazon PA-API with retry logic.

        Args:
            keyword: Search query string
            item_count: Number of results to return (max 10 per request)
            search_index: Amazon search index (All, Electronics, etc.)

        Returns:
            API response as dictionary

        Raises:
            httpx.HTTPStatusError: If API returns error status
            httpx.TimeoutException: If request times out
            httpx.NetworkError: If network error occurs
        """
        # Rate limiting
        await self.rate_limiter.acquire(self.API_DOMAIN)

        # Build request payload
        payload = {
            "Keywords": keyword,
            "Resources": [
                "Images.Primary.Large",
                "ItemInfo.Title",
                "ItemInfo.ByLineInfo",
                "Offers.Listings.Price",
                "Offers.Listings.SavingBasis",
            ],
            "PartnerTag": self.partner_tag,
            "PartnerType": "Associates",
            "Marketplace": self.API_MARKETPLACE,
            "SearchIndex": search_index,
            "ItemCount": min(item_count, 10),  # API max is 10 per request
        }

        # Generate AWS Signature Version 4 headers
        headers = self._sign_request(payload)

        logger.debug(
            "amazon_api_call",
            keyword=keyword,
            item_count=payload["ItemCount"],
        )

        # Make request using context manager for proper cleanup
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    self.API_BASE_URL,
                    headers=headers,
                    json=payload,
                )

                # Handle rate limiting
                if response.status_code == 429:
                    logger.warning("amazon_rate_limit_hit", keyword=keyword)
                    raise httpx.HTTPStatusError(
                        "Rate limit exceeded",
                        request=response.request,
                        response=response,
                    )

                # Raise for other HTTP errors
                response.raise_for_status()

                data = response.json()

                # Check for API-level errors
                if "Errors" in data:
                    error_msg = data["Errors"][0].get("Message", "Unknown error")
                    logger.error("amazon_api_error", keyword=keyword, error=error_msg)
                    raise ValueError(f"Amazon API error: {error_msg}")

                logger.debug(
                    "amazon_api_success",
                    keyword=keyword,
                    returned_items=len(data.get("SearchResult", {}).get("Items", [])),
                )

                return data

        except httpx.HTTPStatusError as e:
            logger.error(
                "amazon_api_http_error",
                status_code=e.response.status_code,
                keyword=keyword,
                error=str(e),
            )
            raise

        except httpx.TimeoutException as e:
            logger.error("amazon_api_timeout", keyword=keyword, error=str(e))
            raise

        except httpx.NetworkError as e:
            logger.error("amazon_api_network_error", keyword=keyword, error=str(e))
            raise

        except Exception as e:
            logger.error("amazon_api_unexpected_error", keyword=keyword, error=str(e))
            raise

    def _sign_request(self, payload: Dict[str, Any]) -> Dict[str, str]:
        """Generate AWS Signature Version 4 headers for Amazon PA-API.

        Args:
            payload: Request payload to be sent

        Returns:
            Dictionary of headers including Authorization
        """
        # Step 1: Create canonical request
        method = "POST"
        canonical_uri = "/paapi5/searchitems"
        canonical_querystring = ""

        # Current timestamp
        t = datetime.utcnow()
        amz_date = t.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = t.strftime("%Y%m%d")

        # Serialize payload
        payload_str = json.dumps(payload, separators=(',', ':'))
        payload_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

        # Headers for canonical request
        canonical_headers = (
            f"content-type:application/json; charset=utf-8\n"
            f"host:{self.API_DOMAIN}\n"
            f"x-amz-date:{amz_date}\n"
            f"x-amz-target:com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems\n"
        )
        signed_headers = "content-type;host;x-amz-date;x-amz-target"

        # Create canonical request
        canonical_request = (
            f"{method}\n"
            f"{canonical_uri}\n"
            f"{canonical_querystring}\n"
            f"{canonical_headers}\n"
            f"{signed_headers}\n"
            f"{payload_hash}"
        )

        # Step 2: Create string to sign
        algorithm = "AWS4-HMAC-SHA256"
        credential_scope = f"{date_stamp}/{self.API_REGION}/{self.API_SERVICE}/aws4_request"
        canonical_request_hash = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()

        string_to_sign = (
            f"{algorithm}\n"
            f"{amz_date}\n"
            f"{credential_scope}\n"
            f"{canonical_request_hash}"
        )

        # Step 3: Calculate signing key
        def sign(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        k_date = sign(f"AWS4{self.secret_key}".encode("utf-8"), date_stamp)
        k_region = sign(k_date, self.API_REGION)
        k_service = sign(k_region, self.API_SERVICE)
        k_signing = sign(k_service, "aws4_request")

        # Step 4: Calculate signature
        signature = hmac.new(
            k_signing,
            string_to_sign.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        # Step 5: Create Authorization header
        authorization_header = (
            f"{algorithm} "
            f"Credential={self.access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )

        # Return headers
        return {
            "Authorization": authorization_header,
            "Content-Type": "application/json; charset=utf-8",
            "Host": self.API_DOMAIN,
            "X-Amz-Date": amz_date,
            "X-Amz-Target": "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems",
        }

    def _normalize_item(
        self, item: Dict[str, Any], category_hint: Optional[str] = None
    ) -> Optional[NormalizedDeal]:
        """Convert Amazon PA-API item to NormalizedDeal.

        Args:
            item: Raw item from Amazon PA-API response
            category_hint: Optional category hint from search keyword

        Returns:
            NormalizedDeal object or None if item is invalid
        """
        # Extract and clean data
        title = item.get("ItemInfo", {}).get("Title", {}).get("DisplayValue", "")
        if not title:
            logger.warning("item_missing_title", item=item)
            return None

        asin = item.get("ASIN", "")
        if not asin:
            logger.warning("item_missing_asin", title=title)
            return None

        # Extract price from Offers
        offers = item.get("Offers", {}).get("Listings", [])
        if not offers:
            logger.debug("item_no_offers", title=title, asin=asin)
            return None

        offer = offers[0]
        price_data = offer.get("Price", {})

        # Price is in USD cents
        price_amount = price_data.get("Amount", 0)
        if not price_amount or price_amount <= 0:
            logger.debug("item_invalid_price", title=title, asin=asin, price_amount=price_amount)
            return None

        # Convert USD cents to KRW
        price_usd = Decimal(str(price_amount))
        deal_price = PriceNormalizer.to_krw(price_usd, "USD")

        # Get original price and calculate discount
        original_price = None
        discount_percentage = None

        # Try SavingBasis first, then Savings
        saved_amount = offer.get("SavingBasis", {}).get("Amount")
        if not saved_amount:
            savings = offer.get("Price", {}).get("Savings", {})
            if savings:
                saved_amount = savings.get("Amount")

        if saved_amount:
            original_price_usd = Decimal(str(saved_amount))
            original_price = PriceNormalizer.to_krw(original_price_usd, "USD")
            discount_percentage = self._calculate_discount_percentage(original_price, deal_price)

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

        # Extract image URL
        image_url = ""
        images = item.get("Images", {}).get("Primary", {})
        if images:
            large_image = images.get("Large", {})
            image_url = large_image.get("URL", "")

        # Extract brand
        brand = None
        by_line_info = item.get("ItemInfo", {}).get("ByLineInfo", {})
        if by_line_info:
            brand_data = by_line_info.get("Brand", {})
            if brand_data:
                brand = brand_data.get("DisplayValue")

        # Create product
        product = NormalizedProduct(
            external_id=asin,
            title=title,
            current_price=deal_price,
            original_price=original_price,
            currency="KRW",
            product_url=item.get("DetailPageURL", ""),
            image_url=image_url,
            brand=brand,
            category_hint=classified_category,
            description=None,
            metadata={
                "asin": asin,
                "parent_asin": item.get("ParentASIN", ""),
            },
        )

        # Create deal
        deal = NormalizedDeal(
            product=product,
            deal_price=deal_price,
            title=title,
            deal_url=item.get("DetailPageURL", ""),
            original_price=original_price,
            discount_percentage=discount_percentage,
            deal_type=deal_type,
            description=None,
            image_url=image_url,
            starts_at=None,
            expires_at=None,
            metadata={
                "asin": asin,
                "parent_asin": item.get("ParentASIN", ""),
                "brand": brand,
            },
        )

        return deal

    async def cleanup(self) -> None:
        """Clean up resources. No persistent resources to clean."""
        pass
