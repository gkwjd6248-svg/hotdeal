"""Lotteon (롯데온) scraper adapter.

Scrapes deals from Lotteon's homepage product cards.
Vue.js SPA — product cards use data-item JSON attribute for product IDs.

Structure: div.productCard
  - data-item={"item_id": "LO...", ...} (JSON with product ID)
  - span.final (price)
  - div.priceBenefitUnit (benefit price)
  - [class*=name] (product name)
  - img (product image)
"""

import json
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

_DEAL_URLS = [
    "https://www.lotteon.com/p/display/main/lotteOn",
    "https://www.lotteon.com/p/display/shop/seltDeal",
    "https://www.lotteon.com",
]

_WAIT_SELECTOR = ", ".join([
    ".productCard",
    "span.final",
    "[class*='product']",
    "[data-item]",
])


class LotteonAdapter(BaseScraperAdapter):
    """Lotteon deal scraper adapter."""

    shop_slug = "lotteon"
    shop_name = "롯데온"
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
        """Fetch current deals from Lotteon."""
        context = await self._get_browser_context()

        all_deals: List[NormalizedDeal] = []
        seen_ids: set = set()

        for url in _DEAL_URLS:
            page = await context.new_page()
            try:
                self.logger.info("trying_lotteon_url", url=url)
                html = await self._safe_scrape(
                    page, url, _WAIT_SELECTOR,
                    scroll=True, wait_seconds=3.0,
                )
                deals = self._parse_deals_from_html(html, seen_ids)
                if deals:
                    all_deals.extend(deals)
                    self.logger.info("lotteon_deals_found", url=url, count=len(deals))
                    break
                else:
                    self.logger.warning("no_deals_at_url", url=url)
            except Exception as e:
                self.logger.warning("lotteon_url_failed", url=url, error=str(e))
            finally:
                try:
                    await page.close()
                except Exception:
                    pass

        self.logger.info("fetched_lotteon_deals_total", count=len(all_deals))
        return all_deals

    def _parse_deals_from_html(self, html: str, seen_ids: set) -> List[NormalizedDeal]:
        """Parse deals from raw HTML."""
        soup = BeautifulSoup(html, "html.parser")
        deals = []

        # Strategy 1 (primary): div.productCard with data-item JSON
        product_cards = soup.select("div.productCard, [class*='productCard']")
        self.logger.info("lotteon_product_cards_found", count=len(product_cards))

        for card in product_cards:
            deal = self._parse_product_card(card, seen_ids)
            if deal:
                deals.append(deal)
                seen_ids.add(deal.product.external_id)

        if deals:
            return deals

        # Strategy 2: elements with data-item attribute
        data_items = soup.select("[data-item]")
        self.logger.info("lotteon_data_items_found", count=len(data_items))

        for elem in data_items:
            deal = self._parse_data_item(elem, seen_ids)
            if deal:
                deals.append(deal)
                seen_ids.add(deal.product.external_id)

        return deals

    def _parse_product_card(self, card, seen_ids: set) -> Optional[NormalizedDeal]:
        """Parse a div.productCard element."""
        try:
            # Extract item_id from data-item JSON attribute
            data_item_str = card.get("data-item", "")
            external_id = None

            if data_item_str:
                try:
                    data_item = json.loads(data_item_str)
                    external_id = data_item.get("item_id")
                except (json.JSONDecodeError, TypeError):
                    pass

            if not external_id or external_id in seen_ids:
                return None

            product_url = f"https://www.lotteon.com/p/product/{external_id}"

            # Title
            title = None
            for sel in ["[class*='name']", "[class*='title']", "[class*='tit']", "p", "span"]:
                elem = card.select_one(sel)
                if elem:
                    text = elem.get_text(strip=True)
                    if text and len(text) > 5 and not re.match(r'^[\d,%원]+$', text):
                        title = text
                        break

            if not title or len(title) < 3:
                return None

            # Prices: span.final (regular price), div.priceBenefitUnit (benefit price)
            current_price = None
            original_price = None

            benefit_elem = card.select_one(".priceBenefitUnit, [class*='benefit']")
            if benefit_elem:
                current_price = PriceNormalizer.clean_price_string(benefit_elem.get_text(strip=True))

            final_elem = card.select_one("span.final, [class*='final']")
            if final_elem:
                price = PriceNormalizer.clean_price_string(final_elem.get_text(strip=True))
                if price:
                    if current_price and price > current_price:
                        original_price = price
                    elif not current_price:
                        current_price = price

            if not current_price:
                # Fallback: find any price-like text
                price_texts = card.find_all(string=re.compile(r'\d{1,3}(,\d{3})+'))
                for pt in price_texts:
                    if pt.parent.name in ('style', 'script'):
                        continue
                    price = PriceNormalizer.clean_price_string(pt.strip())
                    if price and 100 < price < 100_000_000:
                        current_price = price
                        break

            if not current_price:
                return None

            discount_pct = None
            if original_price and original_price > current_price:
                discount_pct = self._calculate_discount_percentage(original_price, current_price)

            # Image
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
                metadata={"source": "homepage"},
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
                metadata={"source": "homepage", "shop": self.shop_name},
            )

        except Exception as e:
            self.logger.debug("parse_product_card_failed", error=str(e))
            return None

    def _parse_data_item(self, elem, seen_ids: set) -> Optional[NormalizedDeal]:
        """Parse an element with data-item attribute (fallback)."""
        try:
            data_item_str = elem.get("data-item", "")
            if not data_item_str:
                return None

            data_item = json.loads(data_item_str)
            external_id = data_item.get("item_id")
            if not external_id or external_id in seen_ids:
                return None

            title = data_item.get("item_name", "")
            if not title or len(title) < 3:
                return None

            price = data_item.get("price")
            if not price:
                return None

            current_price = Decimal(str(price))
            if current_price <= 0:
                return None

            product_url = f"https://www.lotteon.com/p/product/{external_id}"
            category_hint = CategoryClassifier.classify(title)

            product = NormalizedProduct(
                external_id=external_id,
                title=title,
                current_price=current_price,
                product_url=product_url,
                currency="KRW",
                category_hint=category_hint,
                metadata={"source": "data-item"},
            )

            return NormalizedDeal(
                product=product,
                deal_price=current_price,
                title=title,
                deal_url=product_url,
                deal_type="flash_sale",
                metadata={"source": "data-item", "shop": self.shop_name},
            )

        except (json.JSONDecodeError, TypeError, Exception) as e:
            self.logger.debug("parse_data_item_failed", error=str(e))
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
            product_url = f"https://www.lotteon.com/p/product/{external_id}"
            html = await self._safe_scrape(page, product_url, "[class*='product'], h1")
            soup = BeautifulSoup(html, "html.parser")

            title_elem = soup.select_one("[class*='name'], h1, [class*='title']")
            if not title_elem:
                return None
            title = title_elem.get_text(strip=True)

            price_elem = soup.select_one("span.final, [class*='price'] strong, [class*='price'] em")
            if not price_elem:
                return None
            current_price = PriceNormalizer.clean_price_string(price_elem.get_text(strip=True))
            if not current_price or current_price <= 0:
                return None

            original_price = None
            original_elem = soup.select_one("[class*='original'], del")
            if original_elem:
                op = PriceNormalizer.clean_price_string(original_elem.get_text(strip=True))
                if op and op > current_price:
                    original_price = op

            image_url = None
            img_elem = soup.select_one("[class*='product'] img, img[src*='image']")
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
