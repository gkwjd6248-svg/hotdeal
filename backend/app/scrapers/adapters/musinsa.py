"""Musinsa (무신사) scraper adapter.

Scrapes deals from Musinsa's homepage product carousels.
Fashion-focused e-commerce platform (Next.js SPA).

Structure: a[href*='/products/{id}'] inside carousel containers
  - [class*='brand'] for brand name
  - [class*='PriceText'] or text with comma-formatted numbers for price
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
    "https://www.musinsa.com/main/musinsa/sale",
    "https://www.musinsa.com/main/musinsa/ranking",
    "https://www.musinsa.com",
]

_WAIT_SELECTOR = ", ".join([
    "a[href*='/products/']",
    "[class*='product']",
    "[class*='item']",
    "[class*='Carousel']",
])


class MusinsaAdapter(BaseScraperAdapter):
    """Musinsa sale scraper adapter."""

    shop_slug = "musinsa"
    shop_name = "무신사"
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
        """Fetch current deals from Musinsa."""
        context = await self._get_browser_context()

        all_deals: List[NormalizedDeal] = []
        seen_ids: set = set()

        for url in _DEAL_URLS:
            page = await context.new_page()
            try:
                self.logger.info("trying_musinsa_url", url=url)
                html = await self._safe_scrape(
                    page, url, _WAIT_SELECTOR,
                    scroll=True, wait_seconds=3.0,
                )
                deals = self._parse_deals_from_html(html, seen_ids)
                if deals:
                    all_deals.extend(deals)
                    self.logger.info("musinsa_deals_found", url=url, count=len(deals))
                    break
                else:
                    self.logger.warning("no_deals_at_url", url=url)
            except Exception as e:
                self.logger.warning("musinsa_url_failed", url=url, error=str(e))
            finally:
                try:
                    await page.close()
                except Exception:
                    pass

        self.logger.info("fetched_musinsa_deals_total", count=len(all_deals))
        return all_deals

    def _parse_deals_from_html(self, html: str, seen_ids: set) -> List[NormalizedDeal]:
        """Parse deals from raw HTML using multiple strategies."""
        soup = BeautifulSoup(html, "html.parser")
        deals = []

        # Strategy 1: Find product links with /products/{id} pattern
        product_links = soup.select("a[href*='/products/']")
        self.logger.info("musinsa_product_links_found", count=len(product_links))

        for link in product_links:
            deal = self._parse_from_link(link, seen_ids)
            if deal:
                deals.append(deal)
                seen_ids.add(deal.product.external_id)

        if deals:
            return deals

        # Strategy 2: Legacy /goods/ pattern
        legacy_links = soup.select("a[href*='/goods/'], a[href*='goodsNo=']")
        self.logger.info("musinsa_legacy_links_found", count=len(legacy_links))

        for link in legacy_links:
            deal = self._parse_from_legacy_link(link, seen_ids)
            if deal:
                deals.append(deal)
                seen_ids.add(deal.product.external_id)

        return deals

    def _parse_from_link(self, link_elem, seen_ids: set) -> Optional[NormalizedDeal]:
        """Parse a deal from a /products/{id} link element."""
        try:
            href = link_elem.get("href", "")
            if not href:
                return None

            id_match = re.search(r"/products/(\d+)", href)
            if not id_match:
                return None
            external_id = id_match.group(1)

            if external_id in seen_ids:
                return None

            product_url = href
            if not product_url.startswith("http"):
                product_url = f"https://www.musinsa.com{product_url}"

            # Get text from the link itself
            link_text = link_elem.get_text(strip=True)

            # Walk up to find a container with brand and price info
            container = link_elem
            brand = None
            title = None
            current_price = None
            image_url = None

            for _ in range(5):
                if container.parent is None:
                    break
                container = container.parent

                # Check if this level has price info
                price_texts = container.find_all(string=re.compile(r'\d{1,3}(,\d{3})+'))
                if not price_texts:
                    continue

                # Found a container with prices — extract everything
                brand_elem = container.select_one("[class*='brand']")
                if brand_elem:
                    brand = brand_elem.get_text(strip=True)

                # Title: prefer the link text if meaningful, else look for name/title
                if link_text and len(link_text) > 3 and not re.match(r'^[\d,%원]+$', link_text):
                    title = link_text
                else:
                    for sel in ["[class*='name']", "[class*='title']", "[class*='text']"]:
                        elem = container.select_one(sel)
                        if elem:
                            t = elem.get_text(strip=True)
                            if t and len(t) > 3 and not re.match(r'^[\d,%원]+$', t):
                                title = t
                                break

                # Price: find the price-like text
                for pt in price_texts:
                    price = PriceNormalizer.clean_price_string(pt.strip())
                    if price and 100 < price < 100_000_000:
                        current_price = price
                        break

                # Image
                img = container.select_one("img")
                if img:
                    image_url = img.get("src") or img.get("data-src")
                    if image_url and image_url.startswith("//"):
                        image_url = f"https:{image_url}"
                    elif image_url and not image_url.startswith("http"):
                        image_url = None

                break

            if not title and brand:
                title = brand
            if title and brand and brand not in title:
                title = f"{brand} {title}"

            if not title or not current_price:
                return None

            title = re.sub(r'^\d{1,3}(?=[가-힣A-Za-z\[\(])', '', title).strip()
            if len(title) < 3:
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
                deal_type="clearance",
                image_url=image_url,
                metadata={"source": "homepage", "shop": self.shop_name},
            )

        except Exception as e:
            self.logger.debug("parse_from_link_failed", error=str(e))
            return None

    def _parse_from_legacy_link(self, link_elem, seen_ids: set) -> Optional[NormalizedDeal]:
        """Parse from legacy /goods/{id} link pattern."""
        try:
            href = link_elem.get("href", "")
            id_match = re.search(r"goodsNo=(\d+)", href) or re.search(r"/goods/(\d+)", href)
            if not id_match:
                return None
            external_id = id_match.group(1)

            if external_id in seen_ids:
                return None

            product_url = href
            if not product_url.startswith("http"):
                product_url = f"https://www.musinsa.com{product_url}"

            title = link_elem.get_text(strip=True)
            if not title or len(title) < 3:
                return None

            # Try finding price in parent
            container = link_elem.parent
            if container:
                container = container.parent or container

            current_price = None
            if container:
                price_texts = container.find_all(string=re.compile(r'\d{1,3}(,\d{3})+'))
                for pt in price_texts:
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
                metadata={"source": "legacy"},
            )

            return NormalizedDeal(
                product=product,
                deal_price=current_price,
                title=title,
                deal_url=product_url,
                deal_type="clearance",
                metadata={"source": "legacy", "shop": self.shop_name},
            )

        except Exception as e:
            self.logger.debug("parse_legacy_link_failed", error=str(e))
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
            product_url = f"https://www.musinsa.com/products/{external_id}"
            html = await self._safe_scrape(page, product_url, "[class*='product'], h1")
            soup = BeautifulSoup(html, "html.parser")

            brand = None
            brand_elem = soup.select_one("[class*='brand'] a, [class*='brand']")
            if brand_elem:
                brand = brand_elem.get_text(strip=True)

            title_elem = soup.select_one("h1, [class*='title'], [class*='name']")
            if not title_elem:
                return None
            product_name = title_elem.get_text(strip=True)
            title = f"{brand} {product_name}".strip() if brand else product_name

            price_elem = soup.select_one("[class*='price'] em, [class*='price'] strong, [class*='Price']")
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
            img_elem = soup.select_one("[class*='product'] img, img[src*='image']")
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
