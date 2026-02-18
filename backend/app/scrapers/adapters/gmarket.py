"""Gmarket (G마켓) scraper adapter.

Scrapes deals from Gmarket's Super Deal and best-selling sections.
Uses multiple URL strategies since Gmarket is a JS-heavy SPA.
"""

import re
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

# Multiple URL targets — try in order until one yields deals
_DEAL_URLS = [
    "https://www.gmarket.co.kr/n/superdeal",
    "https://www.gmarket.co.kr/n/best",
    "https://m.gmarket.co.kr/n/superdeal",
]

# Broad set of selectors to detect deal cards across Gmarket page layouts
_CARD_SELECTORS = [
    "li[class*='item']",
    ".box__component",
    ".box__item-container",
    "[class*='deal-item']",
    "[class*='superdeal']",
    "a[class*='link__item']",
    ".best-list li",
]

# Combined selector for initial page-load wait (any of these means page loaded)
_WAIT_SELECTOR = ", ".join([
    "[class*='superdeal']",
    "[class*='deal']",
    "[class*='item']",
    ".box__component",
    "a[href*='goodscode']",
])


class GmarketAdapter(BaseScraperAdapter):
    """Gmarket Super Deal scraper adapter."""

    shop_slug = "gmarket"
    shop_name = "G마켓"
    RATE_LIMIT_RPM = 15

    def __init__(self):
        super().__init__()
        self.logger = logger.bind(adapter=self.shop_slug)

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=2, min=3, max=15),
        retry=retry_if_exception_type(Exception),
    )
    async def fetch_deals(self, category: Optional[str] = None) -> List[NormalizedDeal]:
        """Fetch current deals from Gmarket."""
        context = await self._get_browser_context()

        all_deals: List[NormalizedDeal] = []
        seen_ids: set = set()

        all_urls = list(_DEAL_URLS) + ["https://www.gmarket.co.kr"]

        for url in all_urls:
            # Create a fresh page per URL (some pages redirect/close the tab)
            page = await context.new_page()
            try:
                self.logger.info("trying_gmarket_url", url=url)
                html = await self._safe_scrape(
                    page, url, _WAIT_SELECTOR,
                    scroll=True, wait_seconds=3.0,
                )
                deals = self._parse_deals_from_html(html, seen_ids)
                if deals:
                    all_deals.extend(deals)
                    self.logger.info("gmarket_deals_found", url=url, count=len(deals))
                    break
                else:
                    self.logger.warning("no_deals_at_url", url=url)
            except Exception as e:
                self.logger.warning("gmarket_url_failed", url=url, error=str(e))
            finally:
                try:
                    await page.close()
                except Exception:
                    pass

        self.logger.info("fetched_gmarket_deals_total", count=len(all_deals))
        return all_deals

    def _parse_deals_from_html(self, html: str, seen_ids: set) -> List[NormalizedDeal]:
        """Parse deals from raw HTML using multiple selector strategies."""
        soup = BeautifulSoup(html, "html.parser")
        deals = []

        # Strategy 1: Find all links to product pages (most reliable)
        product_links = soup.select("a[href*='goodscode='], a[href*='item.gmarket']")
        self.logger.info("gmarket_product_links_found", count=len(product_links))

        for link in product_links:
            deal = self._parse_from_link(link, seen_ids)
            if deal:
                deals.append(deal)
                seen_ids.add(deal.product.external_id)

        if deals:
            return deals

        # Strategy 2: Find card-like containers
        for selector in _CARD_SELECTORS:
            cards = soup.select(selector)
            if not cards:
                continue
            self.logger.info("trying_card_selector", selector=selector, count=len(cards))
            for card in cards:
                deal = self._parse_deal_card(card, seen_ids)
                if deal:
                    deals.append(deal)
                    seen_ids.add(deal.product.external_id)
            if deals:
                break

        return deals

    def _parse_from_link(self, link_elem, seen_ids: set) -> Optional[NormalizedDeal]:
        """Parse a deal from a product link element and its child elements."""
        try:
            href = link_elem.get("href", "")
            if not href:
                return None

            # Extract product ID
            id_match = re.search(r"goodscode=(\d+)", href) or re.search(r"/item/(\d+)", href)
            if not id_match:
                return None
            external_id = id_match.group(1)

            if external_id in seen_ids:
                return None

            product_url = href
            if not product_url.startswith("http"):
                product_url = f"https://www.gmarket.co.kr{product_url}"

            # Use the link element itself as the container (NOT parent)
            container = link_elem

            # Strategy A: Try to find structured child elements first
            title = None
            current_price = None
            original_price = None
            discount_pct = None
            image_url = None

            # Try title from child elements
            for sel in ["[class*='title']", "[class*='name']", "[class*='text']"]:
                elem = container.select_one(sel)
                if elem:
                    text = elem.get_text(strip=True)
                    # Title should be text without digits-only or % patterns
                    if text and len(text) > 5 and not re.match(r'^[\d,%원]+$', text):
                        title = text
                        break

            # Try price from child elements
            for sel in [
                "[class*='price'] strong", "[class*='sale'] strong",
                "[class*='price']", "[class*='value']",
            ]:
                for elem in container.select(sel):
                    text = elem.get_text(strip=True)
                    price = PriceNormalizer.clean_price_string(text)
                    if price and 100 < price < 100_000_000:
                        current_price = price
                        break
                if current_price:
                    break

            # Try original price from child elements
            for sel in ["del", "s", "[class*='origin']", "[class*='before']"]:
                elem = container.select_one(sel)
                if elem:
                    text = elem.get_text(strip=True)
                    price = PriceNormalizer.clean_price_string(text)
                    if price and price > (current_price or 0):
                        original_price = price
                        break

            # Try discount from child elements
            for sel in ["[class*='discount']", "[class*='rate']", "[class*='percent']"]:
                elem = container.select_one(sel)
                if elem:
                    text = elem.get_text(strip=True)
                    m = re.search(r"(\d+)\s*%", text)
                    if m:
                        discount_pct = Decimal(m.group(1))
                        break

            # Strategy B: If child elements didn't work, parse from flat text
            if not title or not current_price:
                flat_text = container.get_text(strip=True)
                title, current_price, original_price, discount_pct = (
                    self._parse_from_flat_text(flat_text, title, current_price, original_price, discount_pct)
                )

            if not title or not current_price:
                return None

            # Clean title: remove leading rank numbers like "1", "2"
            title = re.sub(r'^\d{1,3}(?=[가-힣A-Za-z\[\(])', '', title).strip()
            if len(title) < 3:
                return None

            if not discount_pct and original_price and original_price > current_price:
                discount_pct = self._calculate_discount_percentage(original_price, current_price)

            # Extract image
            img = container.select_one("img")
            if img:
                image_url = img.get("src") or img.get("data-src") or img.get("data-original")
                if image_url and image_url.startswith("//"):
                    image_url = f"https:{image_url}"
                elif image_url and not image_url.startswith("http"):
                    image_url = None

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
                metadata={"source": "superdeal"},
            )

            return NormalizedDeal(
                product=product,
                deal_price=current_price,
                title=title,
                deal_url=product_url,
                original_price=original_price,
                discount_percentage=discount_pct,
                deal_type="flash_sale",
                image_url=image_url,
                metadata={"source": "superdeal", "shop": self.shop_name},
            )

        except Exception as e:
            self.logger.debug("parse_from_link_failed", error=str(e))
            return None

    def _parse_from_flat_text(
        self, text: str,
        existing_title: Optional[str],
        existing_price: Optional[Decimal],
        existing_original: Optional[Decimal],
        existing_discount: Optional[Decimal],
    ):
        """Extract title, prices, and discount from a combined text string.

        Handles text like: "이기다 불고기 닭가슴살 1kg 26%할인 29,900 판매가 21,830원"
        """
        if not text:
            return existing_title, existing_price, existing_original, existing_discount

        # Extract discount percentage
        discount = existing_discount
        if not discount:
            m = re.search(r'(\d{1,2})\s*%', text)
            if m:
                discount = Decimal(m.group(1))

        # Extract all price-like numbers (Korean format: comma-separated, >= 100)
        price_pattern = r'(\d{1,3}(?:,\d{3})+)'
        price_matches = re.findall(price_pattern, text)
        prices = []
        for pm in price_matches:
            val = Decimal(pm.replace(',', ''))
            if 100 < val < 100_000_000:
                prices.append(val)

        current_price = existing_price
        original_price = existing_original

        if not current_price and prices:
            if len(prices) >= 2:
                # Typically: original, then sale price (sale is smaller)
                original_price = max(prices[:2])
                current_price = min(prices[:2])
            else:
                current_price = prices[0]

        # Extract title: remove price/discount portions from text
        title = existing_title
        if not title:
            # Remove numbers-with-commas, %, 원, 판매가, 할인 patterns
            cleaned = re.sub(r'\d{1,3}(,\d{3})+', '', text)
            cleaned = re.sub(r'\d+%할인', '', cleaned)
            cleaned = re.sub(r'(판매가|정상가|할인|원)', '', cleaned)
            cleaned = re.sub(r'^\d{1,3}\s*', '', cleaned)  # Leading rank
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            if len(cleaned) > 5:
                title = cleaned

        return title, current_price, original_price, discount

    def _parse_deal_card(self, card, seen_ids: set) -> Optional[NormalizedDeal]:
        """Parse a generic card container into a NormalizedDeal."""
        try:
            # Find any product link inside the card
            link_elem = card.select_one("a[href*='goodscode'], a[href*='/item/']")
            if not link_elem:
                # Try any link
                link_elem = card.select_one("a[href]")
            if not link_elem:
                return None

            href = link_elem.get("href", "")
            id_match = re.search(r"goodscode=(\d+)", href) or re.search(r"/item/(\d+)", href)
            if not id_match:
                return None
            external_id = id_match.group(1)

            if external_id in seen_ids:
                return None

            product_url = href
            if not product_url.startswith("http"):
                product_url = f"https://www.gmarket.co.kr{product_url}"

            # Title
            title_elem = (
                card.select_one("[class*='title']") or
                card.select_one("[class*='name']") or
                card.select_one("span") or
                link_elem
            )
            title = title_elem.get_text(strip=True) if title_elem else None
            if not title or len(title) < 3:
                return None

            # Price
            current_price = None
            for sel in ["[class*='price'] strong", "[class*='price']", "strong", "em"]:
                for elem in card.select(sel):
                    text = elem.get_text(strip=True)
                    price = PriceNormalizer.clean_price_string(text)
                    if price and price > 100:
                        current_price = price
                        break
                if current_price:
                    break
            if not current_price:
                return None

            # Original price
            original_price = None
            for sel in ["del", "[class*='original']", "s"]:
                elem = card.select_one(sel)
                if elem:
                    text = elem.get_text(strip=True)
                    price = PriceNormalizer.clean_price_string(text)
                    if price and price > current_price:
                        original_price = price
                        break

            discount_pct = None
            if original_price and original_price > current_price:
                discount_pct = self._calculate_discount_percentage(original_price, current_price)

            image_url = None
            img = card.select_one("img")
            if img:
                image_url = img.get("src") or img.get("data-src")
                if image_url and image_url.startswith("//"):
                    image_url = f"https:{image_url}"
                elif image_url and not image_url.startswith("http"):
                    image_url = None

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
                metadata={"source": "superdeal"},
            )

            return NormalizedDeal(
                product=product,
                deal_price=current_price,
                title=title,
                deal_url=product_url,
                original_price=original_price,
                discount_percentage=discount_pct,
                deal_type="flash_sale",
                image_url=image_url,
                metadata={"source": "superdeal", "shop": self.shop_name},
            )

        except Exception as e:
            self.logger.debug("parse_deal_card_failed", error=str(e))
            return None

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
    )
    async def fetch_product_details(self, external_id: str) -> Optional[NormalizedProduct]:
        """Fetch detailed information for a specific product."""
        context = await self._get_browser_context()
        page = await context.new_page()

        try:
            product_url = f"https://item.gmarket.co.kr/Item?goodscode={external_id}"
            html = await self._safe_scrape(page, product_url, ".itemtit, .item_tit, h1")
            soup = BeautifulSoup(html, "html.parser")

            title_elem = soup.select_one(".itemtit, .item_tit, h1")
            if not title_elem:
                return None
            title = title_elem.get_text(strip=True)

            price_elem = soup.select_one(".price_real strong, .price strong, [class*='price'] strong")
            if not price_elem:
                return None
            current_price = PriceNormalizer.clean_price_string(price_elem.get_text(strip=True))
            if not current_price or current_price <= 0:
                return None

            original_price = None
            original_elem = soup.select_one("del, [class*='original']")
            if original_elem:
                original_price = PriceNormalizer.clean_price_string(original_elem.get_text(strip=True))

            image_url = None
            img_elem = soup.select_one(".item_photo_big img, .thumb_img img, img[src*='image']")
            if img_elem:
                image_url = img_elem.get("src") or img_elem.get("data-src")
                if image_url and image_url.startswith("//"):
                    image_url = f"https:{image_url}"
                elif image_url and not image_url.startswith("http"):
                    image_url = None

            return NormalizedProduct(
                external_id=external_id,
                title=title,
                current_price=current_price,
                product_url=product_url,
                original_price=original_price,
                currency="KRW",
                image_url=image_url,
                category_hint=CategoryClassifier.classify(title),
                metadata={"shop": self.shop_name},
            )

        except Exception as e:
            self.logger.error("fetch_product_details_failed", external_id=external_id, error=str(e))
            return None
        finally:
            await page.close()
