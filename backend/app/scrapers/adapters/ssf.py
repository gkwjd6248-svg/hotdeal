"""SSF Shop (SSF샵) scraper adapter.

Scrapes deals from SSF Shop's homepage.
Fashion-focused e-commerce platform.

Product links use javascript:goToProductDetailCorner('brand', 'productId', ...)
pattern — IDs are extracted via regex from the JS call.
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
    "https://www.ssfshop.com/event/sale",
    "https://www.ssfshop.com/sale",
    "https://www.ssfshop.com",
]

_WAIT_SELECTOR = ", ".join([
    "a[href*='goToProductDetail']",
    "[class*='product']",
    "[class*='item']",
    "img[src*='ssfshop']",
])


class SSFAdapter(BaseScraperAdapter):
    """SSF Shop sale scraper adapter."""

    shop_slug = "ssf"
    shop_name = "SSF샵"
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
        """Fetch current deals from SSF Shop."""
        context = await self._get_browser_context()

        all_deals: List[NormalizedDeal] = []
        seen_ids: set = set()

        for url in _DEAL_URLS:
            page = await context.new_page()
            try:
                self.logger.info("trying_ssf_url", url=url)
                html = await self._safe_scrape(
                    page, url, _WAIT_SELECTOR,
                    scroll=True, wait_seconds=3.0,
                )
                deals = self._parse_deals_from_html(html, seen_ids)
                if deals:
                    all_deals.extend(deals)
                    self.logger.info("ssf_deals_found", url=url, count=len(deals))
                    break
                else:
                    self.logger.warning("no_deals_at_url", url=url)
            except Exception as e:
                self.logger.warning("ssf_url_failed", url=url, error=str(e))
            finally:
                try:
                    await page.close()
                except Exception:
                    pass

        self.logger.info("fetched_ssf_deals_total", count=len(all_deals))
        return all_deals

    def _parse_deals_from_html(self, html: str, seen_ids: set) -> List[NormalizedDeal]:
        """Parse deals from raw HTML."""
        soup = BeautifulSoup(html, "html.parser")
        deals = []

        # Strategy 1: javascript:goToProductDetailCorner links
        js_links = [
            a for a in soup.select("a[href]")
            if "goToProductDetail" in a.get("href", "")
        ]
        self.logger.info("ssf_js_product_links_found", count=len(js_links))

        for link in js_links:
            deal = self._parse_js_link(link, seen_ids)
            if deal:
                deals.append(deal)
                seen_ids.add(deal.product.external_id)

        if deals:
            return deals

        # Strategy 2: links with /goods/ or goodsNo
        product_links = soup.select("a[href*='/goods/'], a[href*='goodsNo=']")
        self.logger.info("ssf_product_links_found", count=len(product_links))

        for link in product_links:
            deal = self._parse_standard_link(link, seen_ids)
            if deal:
                deals.append(deal)
                seen_ids.add(deal.product.external_id)

        return deals

    def _parse_js_link(self, link_elem, seen_ids: set) -> Optional[NormalizedDeal]:
        """Parse a javascript:goToProductDetailCorner link."""
        try:
            href = link_elem.get("href", "")

            # Extract brand and product ID from JS call
            # goToProductDetailCorner('LEBEIGE', 'GM0026010207477', ...)
            m = re.search(r"goToProductDetailCorner\('([^']*)',\s*'([^']*)'", href)
            if not m:
                return None

            brand = m.group(1)
            external_id = m.group(2)

            if not external_id or external_id in seen_ids:
                return None

            product_url = f"https://www.ssfshop.com/{brand}/{external_id}/good"

            # Walk up to find container with title, price, and image
            container = link_elem
            for _ in range(4):
                if container.parent:
                    container = container.parent

            # Title: from link text or child elements
            title = None
            link_text = link_elem.get_text(strip=True)

            # link_text might contain brand+title+prices combined
            # Try to extract title from child elements first
            for sel in ["[class*='name']", "[class*='title']", "[class*='text']"]:
                elem = container.select_one(sel)
                if elem:
                    text = elem.get_text(strip=True)
                    if text and len(text) > 3 and not re.match(r'^[\d,%원]+$', text):
                        title = text
                        break

            if not title and link_text:
                # Clean the combined text — remove price/discount portions
                cleaned = re.sub(r'\d{1,3}(,\d{3})+', '', link_text)
                cleaned = re.sub(r'\d+%', '', cleaned)
                cleaned = re.sub(r'(정가|판매가|할인|원)', '', cleaned)
                cleaned = re.sub(r'\s+', ' ', cleaned).strip()
                if len(cleaned) > 5:
                    title = cleaned

            if not title or len(title) < 3:
                return None

            # Prepend brand if not already in title
            if brand and brand not in title:
                title = f"{brand} {title}"

            # Prices from the container
            current_price = None
            original_price = None

            price_texts = container.find_all(string=re.compile(r'\d{1,3}(,\d{3})+'))
            prices = []
            for pt in price_texts:
                if pt.parent.name in ('style', 'script'):
                    continue
                price = PriceNormalizer.clean_price_string(pt.strip())
                if price and 100 < price < 100_000_000:
                    prices.append(price)

            if len(prices) >= 2:
                original_price = max(prices[:2])
                current_price = min(prices[:2])
            elif prices:
                current_price = prices[0]

            if not current_price:
                return None

            if original_price and original_price <= current_price:
                original_price = None

            discount_pct = None
            if original_price and original_price > current_price:
                discount_pct = self._calculate_discount_percentage(original_price, current_price)

            # Also check for explicit discount percentage
            if not discount_pct:
                disc_match = re.search(r'(\d{1,2})%', link_text or "")
                if disc_match:
                    discount_pct = Decimal(disc_match.group(1))

            # Image
            image_url = None
            img = container.select_one("img")
            if img:
                image_url = img.get("src") or img.get("data-src")
                if image_url and image_url.startswith("//"):
                    image_url = f"https:{image_url}"
                elif image_url and not image_url.startswith("http"):
                    image_url = None

            category_hint = CategoryClassifier.classify(title)
            if not category_hint:
                category_hint = "living-food"

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
                metadata={"source": "homepage"},
            )

            return NormalizedDeal(
                product=product,
                deal_price=current_price,
                title=title,
                deal_url=product_url,
                original_price=original_price,
                discount_percentage=discount_pct,
                deal_type="clearance",
                image_url=image_url,
                metadata={"source": "homepage", "shop": self.shop_name},
            )

        except Exception as e:
            self.logger.debug("parse_js_link_failed", error=str(e))
            return None

    def _parse_standard_link(self, link_elem, seen_ids: set) -> Optional[NormalizedDeal]:
        """Parse a standard /goods/ or goodsNo= link (fallback)."""
        try:
            href = link_elem.get("href", "")
            id_match = re.search(r"goodsNo=(\w+)", href) or re.search(r"/goods/(\w+)", href)
            if not id_match:
                return None
            external_id = id_match.group(1)

            if external_id in seen_ids:
                return None

            product_url = href
            if not product_url.startswith("http"):
                product_url = f"https://www.ssfshop.com{product_url}"

            title = link_elem.get_text(strip=True)
            if not title or len(title) < 3:
                return None

            container = link_elem.parent
            if container:
                container = container.parent or container

            current_price = None
            if container:
                price_texts = container.find_all(string=re.compile(r'\d{1,3}(,\d{3})+'))
                for pt in price_texts:
                    if pt.parent.name in ('style', 'script'):
                        continue
                    price = PriceNormalizer.clean_price_string(pt.strip())
                    if price and 100 < price < 100_000_000:
                        current_price = price
                        break

            if not current_price:
                return None

            category_hint = CategoryClassifier.classify(title)
            if not category_hint:
                category_hint = "living-food"

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
                deal_type="clearance",
                metadata={"source": "link", "shop": self.shop_name},
            )

        except Exception as e:
            self.logger.debug("parse_standard_link_failed", error=str(e))
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
            product_url = f"https://www.ssfshop.com/goods/{external_id}"
            html = await self._safe_scrape(page, product_url, "[class*='product'], h1")
            soup = BeautifulSoup(html, "html.parser")

            brand = None
            brand_elem = soup.select_one("[class*='brand']")
            if brand_elem:
                brand = brand_elem.get_text(strip=True)

            title_elem = soup.select_one("h1, [class*='title'], [class*='name']")
            if not title_elem:
                return None
            product_name = title_elem.get_text(strip=True)
            title = f"{brand} {product_name}".strip() if brand else product_name

            price_elem = soup.select_one("[class*='price'] em, [class*='price'] strong")
            if not price_elem:
                return None
            current_price = PriceNormalizer.clean_price_string(price_elem.get_text(strip=True))
            if not current_price or current_price <= 0:
                return None

            original_price = None
            original_elem = soup.select_one("del, [class*='original']")
            if original_elem:
                op = PriceNormalizer.clean_price_string(original_elem.get_text(strip=True))
                if op and op > current_price:
                    original_price = op

            image_url = None
            img_elem = soup.select_one("[class*='product'] img, img[src*='ssfshop']")
            if img_elem:
                image_url = img_elem.get("src") or img_elem.get("data-src")
                if image_url and image_url.startswith("//"):
                    image_url = f"https:{image_url}"
                elif image_url and not image_url.startswith("http"):
                    image_url = None

            category_hint = CategoryClassifier.classify(title)
            if not category_hint:
                category_hint = "living-food"

            return NormalizedProduct(
                external_id=external_id,
                title=title,
                current_price=current_price,
                product_url=product_url,
                original_price=original_price,
                currency="KRW",
                image_url=image_url,
                brand=brand,
                category_hint=category_hint,
                metadata={"shop": self.shop_name},
            )

        except Exception as e:
            self.logger.error("fetch_product_details_failed", external_id=external_id, error=str(e))
            return None
        finally:
            await page.close()
