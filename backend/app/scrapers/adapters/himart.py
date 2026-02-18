"""Himart (하이마트) scraper adapter.

Scrapes deals from Himart's homepage product listings.
Electronics-focused retailer (Vue.js SPA).

Structure: li.product__item.data--{goodsNo}
  - div.product__thumb > a.product__link > img
  - div.product__info > [class*=title] (product name)
  - span.product__discounted-price (original price)
  - span.product__benefit-price (sale price)
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

_DEAL_URLS = [
    "https://www.e-himart.co.kr/app/display/showEvent",
    "https://www.e-himart.co.kr/app/display/best",
    "https://www.e-himart.co.kr",
]

_WAIT_SELECTOR = ", ".join([
    ".product__item",
    ".product__list",
    "[class*='product']",
    "a[href*='goodsNo']",
])


class HimartAdapter(BaseScraperAdapter):
    """Himart special sale scraper adapter."""

    shop_slug = "himart"
    shop_name = "하이마트"
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
        """Fetch current deals from Himart."""
        context = await self._get_browser_context()

        all_deals: List[NormalizedDeal] = []
        seen_ids: set = set()

        for url in _DEAL_URLS:
            page = await context.new_page()
            try:
                self.logger.info("trying_himart_url", url=url)
                html = await self._safe_scrape(
                    page, url, _WAIT_SELECTOR,
                    scroll=True, wait_seconds=3.0,
                )
                deals = self._parse_deals_from_html(html, seen_ids)
                if deals:
                    all_deals.extend(deals)
                    self.logger.info("himart_deals_found", url=url, count=len(deals))
                    break
                else:
                    self.logger.warning("no_deals_at_url", url=url)
            except Exception as e:
                self.logger.warning("himart_url_failed", url=url, error=str(e))
            finally:
                try:
                    await page.close()
                except Exception:
                    pass

        self.logger.info("fetched_himart_deals_total", count=len(all_deals))
        return all_deals

    def _parse_deals_from_html(self, html: str, seen_ids: set) -> List[NormalizedDeal]:
        """Parse deals from raw HTML using multiple strategies."""
        soup = BeautifulSoup(html, "html.parser")
        deals = []

        # Strategy 1 (primary): li.product__item elements with data--{goodsNo} class
        product_items = soup.select("li.product__item")
        self.logger.info("himart_product_items_found", count=len(product_items))

        for item in product_items:
            deal = self._parse_product_item(item, seen_ids)
            if deal:
                deals.append(deal)
                seen_ids.add(deal.product.external_id)

        if deals:
            return deals

        # Strategy 2: Find links to product detail pages
        product_links = soup.select("a[href*='goodsDetail'], a[href*='goodsNo=']")
        self.logger.info("himart_product_links_found", count=len(product_links))

        for link in product_links:
            deal = self._parse_from_link(link, seen_ids)
            if deal:
                deals.append(deal)
                seen_ids.add(deal.product.external_id)

        return deals

    def _parse_product_item(self, item, seen_ids: set) -> Optional[NormalizedDeal]:
        """Parse a li.product__item element (Himart Vue.js structure)."""
        try:
            # Extract goodsNo from class like 'data--0042613057'
            external_id = None
            for cls in item.get("class", []):
                if cls.startswith("data--"):
                    external_id = cls.replace("data--", "")
                    break

            if not external_id or external_id in seen_ids:
                return None

            product_url = f"https://www.e-himart.co.kr/app/goods/goodsDetail?goodsNo={external_id}"

            # Title from [class*=title] inside .product__info
            title = None
            title_elem = item.select_one("[class*='title']")
            if title_elem:
                title = title_elem.get_text(strip=True)
            if not title or len(title) < 3:
                # Fallback: get text from .product__info minus price portions
                info = item.select_one(".product__info")
                if info:
                    for child in info.select("[class*='price']"):
                        child.decompose()
                    title = info.get_text(strip=True)[:120]

            if not title or len(title) < 3:
                return None

            # Prices: .product__discounted-price = original, .product__benefit-price = sale
            original_price = None
            current_price = None

            disc_elem = item.select_one(".product__discounted-price")
            if disc_elem:
                original_price = PriceNormalizer.clean_price_string(disc_elem.get_text(strip=True))

            bene_elem = item.select_one(".product__benefit-price")
            if bene_elem:
                current_price = PriceNormalizer.clean_price_string(bene_elem.get_text(strip=True))

            # If only discounted price, use it as current price
            if not current_price and original_price:
                current_price = original_price
                original_price = None

            if not current_price:
                return None

            # Ensure original > current
            if original_price and original_price <= current_price:
                original_price = None

            discount_pct = None
            if original_price and original_price > current_price:
                discount_pct = self._calculate_discount_percentage(original_price, current_price)

            # Image
            image_url = None
            img = item.select_one("img")
            if img:
                image_url = img.get("src") or img.get("data-src")
                if image_url and image_url.startswith("//"):
                    image_url = f"https:{image_url}"
                elif image_url and not image_url.startswith("http"):
                    image_url = None

            category_hint = CategoryClassifier.classify(title)
            if not category_hint:
                category_hint = "electronics-tv"

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
                deal_type="price_drop",
                image_url=image_url,
                metadata={"source": "homepage", "shop": self.shop_name},
            )

        except Exception as e:
            self.logger.debug("parse_product_item_failed", error=str(e))
            return None

    def _parse_from_link(self, link_elem, seen_ids: set) -> Optional[NormalizedDeal]:
        """Parse a deal from a product detail link (fallback)."""
        try:
            href = link_elem.get("href", "")
            if not href:
                return None

            id_match = re.search(r"goodsNo=(\d+)", href) or re.search(r"/goods/(\d+)", href)
            if not id_match:
                return None
            external_id = id_match.group(1)

            if external_id in seen_ids:
                return None

            product_url = href
            if not product_url.startswith("http"):
                product_url = f"https://www.e-himart.co.kr{product_url}"

            title = link_elem.get_text(strip=True)
            if not title or len(title) < 5:
                return None

            # Try to find price in siblings/parent
            container = link_elem.parent
            if container:
                container = container.parent or container

            current_price = None
            if container:
                for sel in [".product__benefit-price", ".product__discounted-price", "[class*='price']"]:
                    elem = container.select_one(sel)
                    if elem:
                        price = PriceNormalizer.clean_price_string(elem.get_text(strip=True))
                        if price and price > 100:
                            current_price = price
                            break

            if not current_price:
                return None

            category_hint = CategoryClassifier.classify(title)
            if not category_hint:
                category_hint = "electronics-tv"

            product = NormalizedProduct(
                external_id=external_id,
                title=title,
                current_price=current_price,
                product_url=product_url,
                currency="KRW",
                category_hint=category_hint,
                metadata={"source": "link"},
            )

            return NormalizedDeal(
                product=product,
                deal_price=current_price,
                title=title,
                deal_url=product_url,
                deal_type="price_drop",
                metadata={"source": "link", "shop": self.shop_name},
            )

        except Exception as e:
            self.logger.debug("parse_from_link_failed", error=str(e))
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
            product_url = f"https://www.e-himart.co.kr/app/goods/goodsDetail?goodsNo={external_id}"
            html = await self._safe_scrape(page, product_url, ".product__info, [class*='product']")
            soup = BeautifulSoup(html, "html.parser")

            title_elem = soup.select_one("[class*='title'], h1, .product__name")
            if not title_elem:
                return None
            title = title_elem.get_text(strip=True)

            price_elem = soup.select_one(".product__benefit-price, .product__discounted-price, [class*='price'] strong")
            if not price_elem:
                return None
            current_price = PriceNormalizer.clean_price_string(price_elem.get_text(strip=True))
            if not current_price or current_price <= 0:
                return None

            original_price = None
            original_elem = soup.select_one(".product__discounted-price, del")
            if original_elem:
                op = PriceNormalizer.clean_price_string(original_elem.get_text(strip=True))
                if op and op > current_price:
                    original_price = op

            image_url = None
            img_elem = soup.select_one(".product__thumb img, img[src*='goods']")
            if img_elem:
                image_url = img_elem.get("src") or img_elem.get("data-src")
                if image_url and image_url.startswith("//"):
                    image_url = f"https:{image_url}"
                elif image_url and not image_url.startswith("http"):
                    image_url = None

            category_hint = CategoryClassifier.classify(title)
            if not category_hint:
                category_hint = "electronics-tv"

            return NormalizedProduct(
                external_id=external_id,
                title=title,
                current_price=current_price,
                product_url=product_url,
                original_price=original_price,
                currency="KRW",
                image_url=image_url,
                category_hint=category_hint,
                metadata={"shop": self.shop_name},
            )

        except Exception as e:
            self.logger.error("fetch_product_details_failed", external_id=external_id, error=str(e))
            return None
        finally:
            await page.close()
