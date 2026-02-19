"""AliExpress browser scraper adapter.

Scrapes deals from ko.aliexpress.com (Korean locale) via Playwright.
Uses KRW prices directly (no currency conversion needed).

Anti-bot measures: low RPM (5), random delays 2-5s, CAPTCHA detection.
"""

import asyncio
import random
import re
from decimal import Decimal
from typing import List, Optional

import structlog
from bs4 import BeautifulSoup

try:
    from playwright.async_api import Page, TimeoutError as PlaywrightTimeout
except ImportError:
    Page = None
    PlaywrightTimeout = TimeoutError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.scrapers.base import BaseScraperAdapter, NormalizedDeal, NormalizedProduct
from app.scrapers.utils.normalizer import PriceNormalizer, CategoryClassifier


logger = structlog.get_logger()

_DEAL_URLS = [
    "https://ko.aliexpress.com/wholesale?catId=0&initiative_id=SB_20260219&SearchText=best+deals&sortType=total_tranpro_desc",
    "https://ko.aliexpress.com/category/100003109/women-clothing.html",
    "https://ko.aliexpress.com/category/44/consumer-electronics.html",
    "https://ko.aliexpress.com",
]

_WAIT_SELECTOR = ", ".join([
    "a[href*='/item/']",
    "[class*='product-card']",
    "[class*='search-item']",
    "[class*='CardWrapper']",
    "[class*='Product']",
])

# CAPTCHA / anti-bot indicators
_CAPTCHA_MARKERS = [
    "slide to verify",
    "unusual traffic",
    "captcha",
    "verify you are human",
    "security verification",
    "punish",
]


class AliExpressBrowserAdapter(BaseScraperAdapter):
    """AliExpress deal scraper via Playwright browser automation."""

    shop_slug = "aliexpress"
    shop_name = "알리익스프레스"
    RATE_LIMIT_RPM = 5

    def __init__(self):
        super().__init__()
        self.logger = logger.bind(adapter=self.shop_slug)

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=3, min=5, max=30),
        retry=retry_if_exception_type(Exception),
    )
    async def fetch_deals(self, category: Optional[str] = None) -> List[NormalizedDeal]:
        """Fetch deals from AliExpress Korean locale."""
        context = await self._get_browser_context()

        all_deals: List[NormalizedDeal] = []
        seen_ids: set = set()

        for url in _DEAL_URLS:
            page = await context.new_page()
            try:
                self.logger.info("trying_aliexpress_url", url=url)
                html = await self._safe_scrape(
                    page, url, _WAIT_SELECTOR,
                    scroll=True, wait_seconds=3.0,
                )

                # Check for CAPTCHA
                html_lower = html.lower()
                if any(marker in html_lower for marker in _CAPTCHA_MARKERS):
                    self.logger.warning("aliexpress_captcha_detected", url=url)
                    continue

                deals = self._parse_deals_from_html(html, seen_ids)
                if deals:
                    all_deals.extend(deals)
                    self.logger.info("aliexpress_deals_found", url=url, count=len(deals))

                # Random delay between page loads
                await asyncio.sleep(random.uniform(2.0, 5.0))

                if len(all_deals) >= 50:
                    break
            except Exception as e:
                self.logger.warning("aliexpress_url_failed", url=url, error=str(e))
            finally:
                try:
                    await page.close()
                except Exception:
                    pass

        self.logger.info("fetched_aliexpress_deals_total", count=len(all_deals))
        return all_deals

    def _parse_deals_from_html(self, html: str, seen_ids: set) -> List[NormalizedDeal]:
        """Parse deals from AliExpress HTML."""
        soup = BeautifulSoup(html, "html.parser")
        deals = []

        # Strategy 1: Find product links with /item/ pattern
        product_links = soup.select("a[href*='/item/']")
        self.logger.info("aliexpress_product_links_found", count=len(product_links))

        for link in product_links:
            deal = self._parse_product_link(link, seen_ids)
            if deal:
                deals.append(deal)
                seen_ids.add(deal.product.external_id)

        if deals:
            return deals

        # Strategy 2: Find card containers
        cards = soup.select(
            "[class*='product-card'], [class*='search-item'], "
            "[class*='CardWrapper'], [class*='ProductContainer']"
        )
        self.logger.info("aliexpress_card_containers_found", count=len(cards))

        for card in cards:
            deal = self._parse_card(card, seen_ids)
            if deal:
                deals.append(deal)
                seen_ids.add(deal.product.external_id)

        return deals

    def _extract_product_id(self, href: str) -> Optional[str]:
        """Extract numeric product ID from AliExpress URL."""
        # Pattern: /item/{numeric_id}.html or /item/{numeric_id}
        match = re.search(r'/item/(\d+)', href)
        if match:
            return match.group(1)
        # Pattern: productId=xxx in query string
        match = re.search(r'productId=(\d+)', href)
        if match:
            return match.group(1)
        return None

    def _parse_product_link(self, link_elem, seen_ids: set) -> Optional[NormalizedDeal]:
        """Parse a deal from a product link element."""
        try:
            href = link_elem.get("href", "")
            if not href:
                return None

            external_id = self._extract_product_id(href)
            if not external_id or external_id in seen_ids:
                return None

            product_url = href
            if product_url.startswith("//"):
                product_url = f"https:{product_url}"
            elif not product_url.startswith("http"):
                product_url = f"https://ko.aliexpress.com{product_url}"

            # Walk up to find container with title and price
            container = link_elem
            title = None
            current_price = None
            original_price = None
            discount_pct = None
            image_url = None

            for _ in range(6):
                if container.parent is None:
                    break
                container = container.parent

                # Look for price-like text (KRW: comma-separated thousands)
                price_texts = container.find_all(
                    string=re.compile(r'\d{1,3}(?:,\d{3})+')
                )
                if not price_texts:
                    continue

                # Found price container - extract info
                # Title: look for text content
                for sel in [
                    "[class*='title']", "[class*='name']", "[class*='subject']",
                    "[class*='desc']", "h1", "h2", "h3",
                ]:
                    elem = container.select_one(sel)
                    if elem:
                        t = elem.get_text(strip=True)
                        if t and len(t) > 5 and not re.match(r'^[\d,%원₩\s]+$', t):
                            title = t
                            break

                if not title:
                    link_text = link_elem.get_text(strip=True)
                    if link_text and len(link_text) > 5 and not re.match(r'^[\d,%원₩\s]+$', link_text):
                        title = link_text

                # Price extraction
                prices = []
                for pt in price_texts:
                    price = PriceNormalizer.clean_price_string(pt.strip())
                    if price and 100 < price < 100_000_000:
                        prices.append(price)

                if prices:
                    prices.sort()
                    current_price = prices[0]  # Lowest = deal price
                    if len(prices) > 1 and prices[-1] > current_price:
                        original_price = prices[-1]

                # Discount percentage
                pct_elem = container.find(string=re.compile(r'(\d+)\s*%'))
                if pct_elem:
                    pct_match = re.search(r'(\d+)\s*%', pct_elem)
                    if pct_match:
                        pct_val = int(pct_match.group(1))
                        if 1 <= pct_val <= 99:
                            discount_pct = Decimal(str(pct_val))

                # Image
                img = container.select_one("img")
                if img:
                    image_url = img.get("src") or img.get("data-src")
                    if image_url and image_url.startswith("//"):
                        image_url = f"https:{image_url}"
                    elif image_url and not image_url.startswith("http"):
                        image_url = None

                break

            if not title or not current_price:
                return None

            # Clean title
            title = title[:200].strip()
            if len(title) < 3:
                return None

            category_hint = CategoryClassifier.classify(title)

            product = NormalizedProduct(
                external_id=external_id,
                title=title,
                current_price=current_price,
                product_url=product_url,
                original_price=original_price,
                currency="KRW",
                image_url=image_url,
                category_hint=category_hint,
                metadata={"source": "ko.aliexpress.com"},
            )

            return NormalizedDeal(
                product=product,
                deal_price=current_price,
                original_price=original_price,
                discount_percentage=discount_pct,
                title=title,
                deal_url=product_url,
                deal_type="clearance",
                image_url=image_url,
                metadata={"source": "ko.aliexpress.com", "shop": self.shop_name},
            )

        except Exception as e:
            self.logger.debug("parse_aliexpress_link_failed", error=str(e))
            return None

    def _parse_card(self, card, seen_ids: set) -> Optional[NormalizedDeal]:
        """Parse a deal from a product card container."""
        try:
            # Find product link
            link = card.select_one("a[href*='/item/']")
            if not link:
                return None
            return self._parse_product_link(link, seen_ids)
        except Exception as e:
            self.logger.debug("parse_aliexpress_card_failed", error=str(e))
            return None

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=2, min=3, max=15),
        retry=retry_if_exception_type(Exception),
    )
    async def fetch_product_details(self, external_id: str) -> Optional[NormalizedProduct]:
        """Fetch detailed product info from AliExpress item page."""
        context = await self._get_browser_context()
        page = await context.new_page()

        try:
            url = f"https://ko.aliexpress.com/item/{external_id}.html"
            html = await self._safe_scrape(page, url, "h1, [class*='title']")

            html_lower = html.lower()
            if any(marker in html_lower for marker in _CAPTCHA_MARKERS):
                self.logger.warning("aliexpress_captcha_on_product", external_id=external_id)
                return None

            soup = BeautifulSoup(html, "html.parser")

            title_elem = soup.select_one("h1") or soup.select_one("[class*='title']")
            if not title_elem:
                return None
            title = title_elem.get_text(strip=True)

            # Price
            price_text = None
            for sel in ["[class*='price'] span", "[class*='Price']", "[class*='price']"]:
                elem = soup.select_one(sel)
                if elem:
                    price_text = elem.get_text(strip=True)
                    break

            if not price_text:
                return None

            current_price = PriceNormalizer.clean_price_string(price_text)
            if not current_price or current_price <= 0:
                return None

            image_url = None
            img = soup.select_one("[class*='gallery'] img, [class*='image'] img, img[src*='alicdn']")
            if img:
                image_url = img.get("src") or img.get("data-src")
                if image_url and image_url.startswith("//"):
                    image_url = f"https:{image_url}"
                elif image_url and not image_url.startswith("http"):
                    image_url = None

            return NormalizedProduct(
                external_id=external_id,
                title=title,
                current_price=current_price,
                product_url=url,
                currency="KRW",
                image_url=image_url,
                category_hint=CategoryClassifier.classify(title),
                metadata={"source": "ko.aliexpress.com", "shop": self.shop_name},
            )

        except Exception as e:
            self.logger.error("fetch_product_details_failed", external_id=external_id, error=str(e))
            return None
        finally:
            await page.close()
