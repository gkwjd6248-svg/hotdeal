"""Example scraper adapter implementation.

This is a reference implementation showing how to create a scraper adapter
that inherits from BaseScraperAdapter. Use this as a template for creating
actual shop-specific scrapers.
"""

from typing import List, Optional
from decimal import Decimal
from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraperAdapter, NormalizedProduct, NormalizedDeal
from app.scrapers.utils import PriceNormalizer, CategoryClassifier, normalize_url
from app.scrapers.utils.retry import playwright_retry


class ExampleScraperAdapter(BaseScraperAdapter):
    """Example scraper adapter for reference.

    This shows the typical structure of a scraper adapter:
    1. Define shop metadata (slug, name)
    2. Implement fetch_deals() to scrape deal listings
    3. Implement fetch_product_details() to scrape individual products
    4. Use helper methods from base class and utils
    """

    shop_slug = "example-shop"
    shop_name = "Example Shop"

    async def fetch_deals(self, category: Optional[str] = None) -> List[NormalizedDeal]:
        """Fetch deals from Example Shop.

        Args:
            category: Optional category filter

        Returns:
            List of NormalizedDeal objects
        """
        deals = []

        # Example URL (replace with actual shop URL)
        url = "https://www.example-shop.com/deals"
        if category:
            url += f"?category={category}"

        try:
            # Get browser context and create page
            context = await self._get_browser_context()
            page = await context.new_page()

            # Scrape page with retry and rate limiting
            html = await self._safe_scrape_with_retry(page, url, wait_selector=".deal-item")

            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html, "lxml")

            # Extract deal items (example selectors)
            deal_items = soup.select(".deal-item")

            for item in deal_items:
                try:
                    deal = self._parse_deal_item(item)
                    if deal:
                        deals.append(deal)
                except Exception as e:
                    self.logger.warning("failed_to_parse_deal", error=str(e))
                    continue

            await page.close()

        except Exception as e:
            self.logger.error("fetch_deals_failed", error=str(e), url=url)
            raise

        self.logger.info("fetched_deals", count=len(deals))
        return deals

    async def fetch_product_details(self, external_id: str) -> Optional[NormalizedProduct]:
        """Fetch product details from Example Shop.

        Args:
            external_id: Shop-specific product ID

        Returns:
            NormalizedProduct or None if not found
        """
        url = f"https://www.example-shop.com/product/{external_id}"

        try:
            # Get browser context and create page
            context = await self._get_browser_context()
            page = await context.new_page()

            # Scrape page with retry and rate limiting
            html = await self._safe_scrape_with_retry(page, url, wait_selector=".product-detail")

            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html, "lxml")

            # Extract product details (example selectors)
            product = self._parse_product_detail(soup, external_id)

            await page.close()
            return product

        except Exception as e:
            self.logger.error("fetch_product_failed", error=str(e), external_id=external_id)
            return None

    @playwright_retry
    async def _safe_scrape_with_retry(self, page, url: str, wait_selector: Optional[str] = None) -> str:
        """Wrapper around _safe_scrape with retry decorator."""
        return await self._safe_scrape(page, url, wait_selector)

    def _parse_deal_item(self, item) -> Optional[NormalizedDeal]:
        """Parse a deal item from BeautifulSoup element.

        Args:
            item: BeautifulSoup element representing a deal

        Returns:
            NormalizedDeal or None if parsing fails
        """
        try:
            # Example parsing (replace with actual selectors)
            title = item.select_one(".deal-title").get_text(strip=True)
            deal_url = item.select_one("a")["href"]
            deal_url = normalize_url(deal_url)

            # Parse prices
            price_text = item.select_one(".price").get_text(strip=True)
            original_price_text = item.select_one(".original-price").get_text(strip=True)

            deal_price = PriceNormalizer.clean_price_string(price_text)
            original_price = PriceNormalizer.clean_price_string(original_price_text)

            if not deal_price:
                return None

            # Extract product info
            external_id = self._extract_product_id(deal_url)
            image_url = item.select_one("img")["src"] if item.select_one("img") else None

            # Create product
            product = NormalizedProduct(
                external_id=external_id,
                title=title,
                current_price=deal_price,
                product_url=deal_url,
                original_price=original_price,
                currency="KRW",
                image_url=image_url,
                category_hint=CategoryClassifier.classify(title),
            )

            # Calculate discount
            discount = self._calculate_discount_percentage(original_price, deal_price)

            # Create deal
            deal = NormalizedDeal(
                product=product,
                deal_price=deal_price,
                title=title,
                deal_url=deal_url,
                original_price=original_price,
                discount_percentage=discount,
                deal_type="price_drop",
                image_url=image_url,
            )

            return deal

        except Exception as e:
            self.logger.debug("parse_deal_item_failed", error=str(e))
            return None

    def _parse_product_detail(self, soup, external_id: str) -> Optional[NormalizedProduct]:
        """Parse product details from BeautifulSoup object.

        Args:
            soup: BeautifulSoup object
            external_id: Product ID

        Returns:
            NormalizedProduct or None if parsing fails
        """
        try:
            # Example parsing (replace with actual selectors)
            title = soup.select_one(".product-title").get_text(strip=True)
            price_text = soup.select_one(".product-price").get_text(strip=True)
            original_price_text = soup.select_one(".original-price")

            current_price = PriceNormalizer.clean_price_string(price_text)
            original_price = None
            if original_price_text:
                original_price = PriceNormalizer.clean_price_string(
                    original_price_text.get_text(strip=True)
                )

            if not current_price:
                return None

            # Extract additional info
            image_url = soup.select_one(".product-image img")["src"]
            brand = soup.select_one(".brand-name")
            brand_name = brand.get_text(strip=True) if brand else None
            description = soup.select_one(".description")
            description_text = description.get_text(strip=True) if description else None

            product_url = f"https://www.example-shop.com/product/{external_id}"

            product = NormalizedProduct(
                external_id=external_id,
                title=title,
                current_price=current_price,
                product_url=normalize_url(product_url),
                original_price=original_price,
                currency="KRW",
                image_url=image_url,
                brand=brand_name,
                category_hint=CategoryClassifier.classify(title),
                description=description_text,
            )

            return product

        except Exception as e:
            self.logger.debug("parse_product_failed", error=str(e))
            return None

    def _extract_product_id(self, url: str) -> str:
        """Extract product ID from URL.

        Args:
            url: Product or deal URL

        Returns:
            Product ID string
        """
        # Example: extract ID from URL pattern
        # Replace with actual logic based on shop URL structure
        import re

        match = re.search(r"/product/(\w+)", url)
        if match:
            return match.group(1)

        # Fallback: use hash of URL
        import hashlib

        return hashlib.md5(url.encode()).hexdigest()[:16]
