"""Lotteon (롯데온) scraper adapter.

Scrapes deals from Lotteon's time-limited special deals section.
"""

from decimal import Decimal
from typing import List, Optional

import structlog
from bs4 import BeautifulSoup
try:
    from playwright.async_api import Page
except ImportError:
    Page = None
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.scrapers.base import BaseScraperAdapter, NormalizedDeal, NormalizedProduct
from app.scrapers.utils.normalizer import PriceNormalizer, CategoryClassifier


logger = structlog.get_logger()


class LotteonAdapter(BaseScraperAdapter):
    """Lotteon time-limited deal scraper adapter."""

    shop_slug = "lotteon"
    shop_name = "롯데온"

    DEALS_URL = "https://www.lotteon.com/p/display/main/lotteOn"
    WAIT_SELECTOR = ".product-item, .timesale, .prd_info"
    RATE_LIMIT_RPM = 10

    def __init__(self):
        """Initialize Lotteon adapter."""
        super().__init__()
        self.logger = logger.bind(adapter=self.shop_slug)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
    )
    async def fetch_deals(self, category: Optional[str] = None) -> List[NormalizedDeal]:
        """Fetch current deals from Lotteon time sales.

        Args:
            category: Optional category filter (not used for Lotteon)

        Returns:
            List of NormalizedDeal objects

        Raises:
            AdapterError: If scraping fails after retries
        """
        context = await self._get_browser_context()
        page = await context.new_page()

        try:
            self.logger.info("fetching_lotteon_deals", url=self.DEALS_URL)

            # Scrape the deals page
            html = await self._safe_scrape(page, self.DEALS_URL, self.WAIT_SELECTOR)
            soup = BeautifulSoup(html, "html.parser")

            deals = []
            seen_ids = set()

            # Parse product cards - multiple selector strategies
            deal_cards = (
                soup.select(".product-item") or
                soup.select(".prd_info") or
                soup.select(".timesale_item")
            )

            self.logger.info("found_deal_cards", count=len(deal_cards))

            for card in deal_cards:
                try:
                    deal = self._parse_deal_card(card)
                    if deal and deal.product.external_id not in seen_ids:
                        deals.append(deal)
                        seen_ids.add(deal.product.external_id)
                except Exception as e:
                    self.logger.warning("failed_to_parse_deal_card", error=str(e))
                    continue

            self.logger.info("fetched_lotteon_deals", count=len(deals))
            return deals

        finally:
            await page.close()

    def _parse_deal_card(self, card) -> Optional[NormalizedDeal]:
        """Parse a deal card element into NormalizedDeal.

        Args:
            card: BeautifulSoup element representing a deal card

        Returns:
            NormalizedDeal or None if parsing fails
        """
        try:
            # Extract product link and ID
            link_elem = card.select_one("a[href*='prdNo'], a[href*='/pd/']")
            if not link_elem or not link_elem.get("href"):
                return None

            product_url = link_elem["href"]
            if not product_url.startswith("http"):
                product_url = f"https://www.lotteon.com{product_url}"

            # Extract product ID from URL (prdNo parameter or path)
            import re
            id_match = re.search(r"prdNo=(\d+)", product_url) or re.search(r"/pd/(\d+)", product_url)
            if not id_match:
                return None
            external_id = id_match.group(1)

            # Extract title
            title_elem = (
                card.select_one(".prd_name a") or
                card.select_one(".product-name") or
                card.select_one(".title")
            )
            if not title_elem:
                return None
            title = title_elem.get_text(strip=True)

            # Extract current price
            price_elem = (
                card.select_one(".sale_price strong") or
                card.select_one(".price_real em") or
                card.select_one(".price strong")
            )
            if not price_elem:
                return None

            price_text = price_elem.get_text(strip=True)
            current_price = PriceNormalizer.clean_price_string(price_text)
            if not current_price or current_price <= 0:
                return None

            # Extract original price (optional)
            original_price = None
            original_elem = (
                card.select_one(".org_price") or
                card.select_one(".price_org del") or
                card.select_one(".original del")
            )
            if original_elem:
                original_text = original_elem.get_text(strip=True)
                original_price = PriceNormalizer.clean_price_string(original_text)

            # Extract discount percentage (optional)
            discount_pct = None
            discount_elem = (
                card.select_one(".rate") or
                card.select_one(".discount_rate") or
                card.select_one(".sale_rate em")
            )
            if discount_elem:
                discount_text = discount_elem.get_text(strip=True)
                discount_match = re.search(r"(\d+)%", discount_text)
                if discount_match:
                    discount_pct = Decimal(discount_match.group(1))

            # Calculate discount if we have both prices but no explicit discount
            if not discount_pct and original_price and original_price > current_price:
                discount_pct = self._calculate_discount_percentage(original_price, current_price)

            # Extract image URL
            image_url = None
            img_elem = card.select_one("img")
            if img_elem:
                image_url = img_elem.get("src") or img_elem.get("data-src") or img_elem.get("data-original")
                if image_url and not image_url.startswith("http"):
                    image_url = f"https:{image_url}" if image_url.startswith("//") else f"https://www.lotteon.com{image_url}"

            # Auto-categorize
            category_hint = CategoryClassifier.classify(title)

            # Create normalized product
            product = NormalizedProduct(
                external_id=external_id,
                title=title,
                current_price=current_price,
                product_url=product_url,
                original_price=original_price,
                currency="KRW",
                image_url=image_url,
                category_hint=category_hint,
                metadata={"source": "timesale"}
            )

            # Create normalized deal
            deal = NormalizedDeal(
                product=product,
                deal_price=current_price,
                title=title,
                deal_url=product_url,
                original_price=original_price,
                discount_percentage=discount_pct,
                deal_type="flash_sale",
                image_url=image_url,
                metadata={"source": "timesale", "shop": self.shop_name}
            )

            return deal

        except Exception as e:
            self.logger.warning("parse_deal_card_failed", error=str(e))
            return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
    )
    async def fetch_product_details(self, external_id: str) -> Optional[NormalizedProduct]:
        """Fetch detailed information for a specific product.

        Args:
            external_id: Lotteon product ID (prdNo)

        Returns:
            NormalizedProduct or None if not found
        """
        context = await self._get_browser_context()
        page = await context.new_page()

        try:
            product_url = f"https://www.lotteon.com/p/product/{external_id}"
            self.logger.info("fetching_product_details", external_id=external_id, url=product_url)

            html = await self._safe_scrape(page, product_url, ".prod_name, .product_tit")
            soup = BeautifulSoup(html, "html.parser")

            # Extract title
            title_elem = soup.select_one(".prod_name, .product_tit h2")
            if not title_elem:
                return None
            title = title_elem.get_text(strip=True)

            # Extract current price
            price_elem = soup.select_one(".sale_price strong, .price_real em")
            if not price_elem:
                return None

            price_text = price_elem.get_text(strip=True)
            current_price = PriceNormalizer.clean_price_string(price_text)
            if not current_price or current_price <= 0:
                return None

            # Extract original price
            original_price = None
            original_elem = soup.select_one(".org_price, .price_org del")
            if original_elem:
                original_text = original_elem.get_text(strip=True)
                original_price = PriceNormalizer.clean_price_string(original_text)

            # Extract image
            image_url = None
            img_elem = soup.select_one(".prod_img img, .detail_img img")
            if img_elem:
                image_url = img_elem.get("src") or img_elem.get("data-src")
                if image_url and not image_url.startswith("http"):
                    image_url = f"https:{image_url}" if image_url.startswith("//") else None

            # Extract brand (optional)
            brand = None
            brand_elem = soup.select_one(".brand_name, .seller_info .name")
            if brand_elem:
                brand = brand_elem.get_text(strip=True)

            # Extract description snippet
            description = None
            desc_elem = soup.select_one(".prod_detail, .product_detail")
            if desc_elem:
                description = desc_elem.get_text(strip=True)[:500]  # Limit to 500 chars

            # Auto-categorize
            category_hint = CategoryClassifier.classify(title)

            product = NormalizedProduct(
                external_id=external_id,
                title=title,
                current_price=current_price,
                product_url=product_url,
                original_price=original_price,
                currency="KRW",
                image_url=image_url,
                brand=brand,
                category_hint=category_hint,
                description=description,
                metadata={"shop": self.shop_name}
            )

            return product

        except Exception as e:
            self.logger.error("fetch_product_details_failed", external_id=external_id, error=str(e))
            return None

        finally:
            await page.close()
