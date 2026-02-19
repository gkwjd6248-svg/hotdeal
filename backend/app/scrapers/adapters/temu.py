"""Temu (테무) scraper adapter.

Scrapes deals from www.temu.com/kr (Korean locale) via Playwright.
Temu is a Next.js app, so __NEXT_DATA__ JSON parsing is the primary strategy.

Anti-bot measures: Cloudflare detection, low RPM (5), random delays 3-6s.
"""

import asyncio
import json
import random
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional

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
    "https://www.temu.com/kr/best-sellers.html",
    "https://www.temu.com/kr/flash-sale.html",
    "https://www.temu.com/kr/trending.html",
    "https://www.temu.com/kr",
]

_WAIT_SELECTOR = ", ".join([
    "a[href*='/goods-']",
    "a[href*='-g-']",
    "[class*='product']",
    "[class*='goods']",
    "[class*='ProductList']",
])

# Cloudflare / anti-bot indicators
_BLOCK_MARKERS = [
    "checking your browser",
    "please wait",
    "security check",
    "captcha",
    "verify you are human",
    "access denied",
    "cf-browser-verification",
]


class TemuAdapter(BaseScraperAdapter):
    """Temu deal scraper via Playwright browser automation."""

    shop_slug = "temu"
    shop_name = "테무"
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
        """Fetch deals from Temu Korean locale."""
        context = await self._get_browser_context()

        all_deals: List[NormalizedDeal] = []
        seen_ids: set = set()

        for url in _DEAL_URLS:
            page = await context.new_page()
            try:
                self.logger.info("trying_temu_url", url=url)
                html = await self._safe_scrape(
                    page, url, _WAIT_SELECTOR,
                    scroll=True, wait_seconds=4.0,
                )

                # Check for Cloudflare block
                html_lower = html.lower()
                if any(marker in html_lower for marker in _BLOCK_MARKERS):
                    self.logger.warning("temu_blocked", url=url)
                    continue

                # Strategy 1: Try __NEXT_DATA__ JSON (most reliable)
                deals = self._parse_next_data(html, seen_ids)

                # Strategy 2: Fall back to HTML parsing
                if not deals:
                    deals = self._parse_deals_from_html(html, seen_ids)

                if deals:
                    all_deals.extend(deals)
                    self.logger.info("temu_deals_found", url=url, count=len(deals))

                # Random delay between page loads
                await asyncio.sleep(random.uniform(3.0, 6.0))

                if len(all_deals) >= 50:
                    break
            except Exception as e:
                self.logger.warning("temu_url_failed", url=url, error=str(e))
            finally:
                try:
                    await page.close()
                except Exception:
                    pass

        self.logger.info("fetched_temu_deals_total", count=len(all_deals))
        return all_deals

    def _parse_next_data(self, html: str, seen_ids: set) -> List[NormalizedDeal]:
        """Parse deals from __NEXT_DATA__ JSON embedded in the page."""
        deals = []

        match = re.search(
            r'<script\s+id="__NEXT_DATA__"\s+type="application/json">(.*?)</script>',
            html, re.DOTALL,
        )
        if not match:
            return deals

        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            self.logger.warning("temu_next_data_parse_failed")
            return deals

        # Walk the JSON to find product/goods arrays
        products = self._extract_products_from_json(data)
        self.logger.info("temu_next_data_products", count=len(products))

        for prod in products:
            deal = self._json_product_to_deal(prod, seen_ids)
            if deal:
                deals.append(deal)
                seen_ids.add(deal.product.external_id)

        return deals

    def _extract_products_from_json(self, data: Any, depth: int = 0) -> List[Dict]:
        """Recursively find product-like objects in JSON data."""
        if depth > 10:
            return []

        products = []

        if isinstance(data, dict):
            # Check if this dict looks like a product
            has_id = any(k in data for k in ("goodsId", "goods_id", "productId", "product_id", "id"))
            has_price = any(k in data for k in ("price", "salePrice", "sale_price", "minPrice", "min_price"))
            has_title = any(k in data for k in ("title", "goodsName", "goods_name", "name", "productName"))

            if has_id and has_price and has_title:
                products.append(data)

            # Recurse into values
            for v in data.values():
                products.extend(self._extract_products_from_json(v, depth + 1))

        elif isinstance(data, list):
            for item in data[:200]:  # Limit to prevent runaway
                products.extend(self._extract_products_from_json(item, depth + 1))

        return products

    def _json_product_to_deal(self, prod: Dict, seen_ids: set) -> Optional[NormalizedDeal]:
        """Convert a JSON product object to a NormalizedDeal."""
        try:
            # Extract ID
            external_id = str(
                prod.get("goodsId") or prod.get("goods_id") or
                prod.get("productId") or prod.get("product_id") or
                prod.get("id", "")
            )
            if not external_id or external_id in seen_ids:
                return None

            # Extract title
            title = (
                prod.get("title") or prod.get("goodsName") or
                prod.get("goods_name") or prod.get("name") or
                prod.get("productName", "")
            )
            if not title or len(str(title)) < 3:
                return None
            title = str(title)[:200].strip()

            # Extract price (KRW expected for /kr locale)
            raw_price = (
                prod.get("salePrice") or prod.get("sale_price") or
                prod.get("price") or prod.get("minPrice") or
                prod.get("min_price")
            )
            if raw_price is None:
                return None

            # Price might be in cents (integer) or already formatted
            price_val = Decimal(str(raw_price))
            # Temu sometimes returns price in cents (e.g., 1299 = $12.99)
            # For KRW locale, prices should be whole numbers > 100
            if price_val <= 0:
                return None
            # If price seems too small for KRW, it might be in a different unit
            if price_val < 100:
                price_val = price_val * 100  # Assume cents

            current_price = price_val

            # Original price
            original_price = None
            raw_orig = (
                prod.get("originPrice") or prod.get("origin_price") or
                prod.get("originalPrice") or prod.get("marketPrice") or
                prod.get("market_price")
            )
            if raw_orig:
                orig_val = Decimal(str(raw_orig))
                if orig_val > current_price:
                    original_price = orig_val
                elif orig_val < 100 and orig_val > 0:
                    orig_val = orig_val * 100
                    if orig_val > current_price:
                        original_price = orig_val

            # Discount
            discount_pct = None
            if original_price and original_price > current_price:
                discount_pct = ((original_price - current_price) / original_price * 100).quantize(Decimal("1"))

            # Image
            image_url = (
                prod.get("image") or prod.get("imageUrl") or
                prod.get("image_url") or prod.get("thumb") or
                prod.get("thumbUrl")
            )
            if image_url:
                image_url = str(image_url)
                if image_url.startswith("//"):
                    image_url = f"https:{image_url}"
                elif not image_url.startswith("http"):
                    image_url = None

            # Product URL
            product_url = f"https://www.temu.com/kr/goods-{external_id}.html"

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
                metadata={"source": "temu_next_data"},
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
                metadata={"source": "temu_next_data", "shop": self.shop_name},
            )

        except Exception as e:
            self.logger.debug("temu_json_product_failed", error=str(e))
            return None

    def _parse_deals_from_html(self, html: str, seen_ids: set) -> List[NormalizedDeal]:
        """Fallback: parse deals from HTML elements."""
        soup = BeautifulSoup(html, "html.parser")
        deals = []

        # Find product links
        product_links = soup.select("a[href*='/goods-'], a[href*='-g-']")
        self.logger.info("temu_html_product_links", count=len(product_links))

        for link in product_links:
            deal = self._parse_html_product(link, seen_ids)
            if deal:
                deals.append(deal)
                seen_ids.add(deal.product.external_id)

        return deals

    def _extract_temu_id(self, href: str) -> Optional[str]:
        """Extract product ID from Temu URL patterns."""
        # Pattern: /goods-{id}.html or -g-{id}.html
        match = re.search(r'/goods-(\d+)', href)
        if match:
            return match.group(1)
        match = re.search(r'-g-(\d+)', href)
        if match:
            return match.group(1)
        return None

    def _parse_html_product(self, link_elem, seen_ids: set) -> Optional[NormalizedDeal]:
        """Parse a deal from an HTML product link."""
        try:
            href = link_elem.get("href", "")
            if not href:
                return None

            external_id = self._extract_temu_id(href)
            if not external_id or external_id in seen_ids:
                return None

            product_url = href
            if product_url.startswith("//"):
                product_url = f"https:{product_url}"
            elif not product_url.startswith("http"):
                product_url = f"https://www.temu.com{product_url}"

            # Walk up to find container
            container = link_elem
            title = None
            current_price = None
            original_price = None
            image_url = None

            for _ in range(6):
                if container.parent is None:
                    break
                container = container.parent

                price_texts = container.find_all(
                    string=re.compile(r'\d{1,3}(?:,\d{3})+')
                )
                if not price_texts:
                    continue

                # Title
                for sel in ["[class*='title']", "[class*='name']", "[class*='desc']"]:
                    elem = container.select_one(sel)
                    if elem:
                        t = elem.get_text(strip=True)
                        if t and len(t) > 5 and not re.match(r'^[\d,%원₩\s]+$', t):
                            title = t
                            break

                if not title:
                    link_text = link_elem.get_text(strip=True)
                    if link_text and len(link_text) > 5:
                        title = link_text

                # Prices
                prices = []
                for pt in price_texts:
                    price = PriceNormalizer.clean_price_string(pt.strip())
                    if price and 100 < price < 100_000_000:
                        prices.append(price)

                if prices:
                    prices.sort()
                    current_price = prices[0]
                    if len(prices) > 1 and prices[-1] > current_price:
                        original_price = prices[-1]

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

            title = title[:200].strip()

            discount_pct = None
            if original_price and original_price > current_price:
                discount_pct = ((original_price - current_price) / original_price * 100).quantize(Decimal("1"))

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
                metadata={"source": "temu_html"},
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
                metadata={"source": "temu_html", "shop": self.shop_name},
            )

        except Exception as e:
            self.logger.debug("parse_temu_html_failed", error=str(e))
            return None

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=2, min=3, max=15),
        retry=retry_if_exception_type(Exception),
    )
    async def fetch_product_details(self, external_id: str) -> Optional[NormalizedProduct]:
        """Fetch detailed product info from Temu item page."""
        context = await self._get_browser_context()
        page = await context.new_page()

        try:
            url = f"https://www.temu.com/kr/goods-{external_id}.html"
            html = await self._safe_scrape(page, url, "h1, [class*='title']")

            html_lower = html.lower()
            if any(marker in html_lower for marker in _BLOCK_MARKERS):
                self.logger.warning("temu_blocked_on_product", external_id=external_id)
                return None

            # Try __NEXT_DATA__ first
            match = re.search(
                r'<script\s+id="__NEXT_DATA__"\s+type="application/json">(.*?)</script>',
                html, re.DOTALL,
            )
            if match:
                try:
                    data = json.loads(match.group(1))
                    products = self._extract_products_from_json(data)
                    for prod in products:
                        pid = str(
                            prod.get("goodsId") or prod.get("goods_id") or
                            prod.get("productId") or prod.get("id", "")
                        )
                        if pid == external_id:
                            deal = self._json_product_to_deal(prod, set())
                            if deal:
                                return deal.product
                except json.JSONDecodeError:
                    pass

            # Fallback: HTML parsing
            soup = BeautifulSoup(html, "html.parser")

            title_elem = soup.select_one("h1") or soup.select_one("[class*='title']")
            if not title_elem:
                return None
            title = title_elem.get_text(strip=True)

            price_elem = soup.select_one("[class*='price']")
            if not price_elem:
                return None

            current_price = PriceNormalizer.clean_price_string(price_elem.get_text(strip=True))
            if not current_price or current_price <= 0:
                return None

            image_url = None
            img = soup.select_one("[class*='gallery'] img, [class*='image'] img")
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
                metadata={"source": "temu_product_page", "shop": self.shop_name},
            )

        except Exception as e:
            self.logger.error("fetch_product_details_failed", external_id=external_id, error=str(e))
            return None
        finally:
            await page.close()
