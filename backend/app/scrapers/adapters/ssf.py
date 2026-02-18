"""SSF Shop (SSF샵) scraper adapter.

Scrapes deals from SSF Shop's sale section.
Fashion-focused e-commerce platform. Uses multiple URL strategies.
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
    "https://m.ssfshop.com/event/sale",
]

_CARD_SELECTORS = [
    ".product-item",
    ".prd-item",
    ".sale-list li",
    "li[class*='item']",
    "[class*='product']",
]

_WAIT_SELECTOR = ", ".join([
    ".product-item",
    ".prd-item",
    "[class*='item']",
    "a[href*='/goods/']",
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

        all_urls = list(_DEAL_URLS) + ["https://www.ssfshop.com"]

        for url in all_urls:
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
        """Parse deals from raw HTML using multiple strategies."""
        soup = BeautifulSoup(html, "html.parser")
        deals = []

        # Strategy 1: Find all links to product pages
        product_links = soup.select("a[href*='/goods/'], a[href*='goodsNo=']")
        self.logger.info("ssf_product_links_found", count=len(product_links))

        for link in product_links:
            deal = self._parse_from_link(link, seen_ids)
            if deal:
                deals.append(deal)
                seen_ids.add(deal.product.external_id)

        if deals:
            return deals

        # Strategy 2: card containers
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
        """Parse a deal from a product link element."""
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
                product_url = f"https://www.ssfshop.com{product_url}"

            container = link_elem
            title = None
            brand = None
            current_price = None
            original_price = None
            discount_pct = None
            image_url = None

            # Try brand
            brand_elem = container.select_one("[class*='brand']")
            if brand_elem:
                brand = brand_elem.get_text(strip=True)

            # Try title
            for sel in ["[class*='name']", "[class*='title']", "[class*='text']"]:
                elem = container.select_one(sel)
                if elem:
                    text = elem.get_text(strip=True)
                    if text and len(text) > 3 and not re.match(r'^[\d,%원]+$', text):
                        title = text
                        break

            if title and brand and brand not in title:
                title = f"{brand} {title}"

            # Try price
            for sel in [
                "[class*='price'] strong", "[class*='sale'] strong",
                "[class*='price'] em", "[class*='price']",
            ]:
                for elem in container.select(sel):
                    text = elem.get_text(strip=True)
                    price = PriceNormalizer.clean_price_string(text)
                    if price and 100 < price < 100_000_000:
                        current_price = price
                        break
                if current_price:
                    break

            # Try original price
            for sel in ["del", "s", "[class*='origin']", "[class*='before']"]:
                elem = container.select_one(sel)
                if elem:
                    text = elem.get_text(strip=True)
                    price = PriceNormalizer.clean_price_string(text)
                    if price and price > (current_price or 0):
                        original_price = price
                        break

            # Try discount
            for sel in ["[class*='discount']", "[class*='rate']", "[class*='percent']"]:
                elem = container.select_one(sel)
                if elem:
                    text = elem.get_text(strip=True)
                    m = re.search(r"(\d+)\s*%", text)
                    if m:
                        discount_pct = Decimal(m.group(1))
                        break

            # Fallback: flat text
            if not title or not current_price:
                flat_text = container.get_text(strip=True)
                title, current_price, original_price, discount_pct = (
                    self._parse_from_flat_text(flat_text, title, current_price, original_price, discount_pct)
                )

            if not title or not current_price:
                return None

            title = re.sub(r'^\d{1,3}(?=[가-힣A-Za-z\[\(])', '', title).strip()
            if len(title) < 3:
                return None

            if not discount_pct and original_price and original_price > current_price:
                discount_pct = self._calculate_discount_percentage(original_price, current_price)

            img = container.select_one("img")
            if img:
                image_url = img.get("src") or img.get("data-src") or img.get("data-original")
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
                metadata={"source": "sale"},
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
                metadata={"source": "sale", "shop": self.shop_name},
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
        """Extract title, prices, and discount from a combined text string."""
        if not text:
            return existing_title, existing_price, existing_original, existing_discount

        discount = existing_discount
        if not discount:
            m = re.search(r'(\d{1,2})\s*%', text)
            if m:
                discount = Decimal(m.group(1))

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
                original_price = max(prices[:2])
                current_price = min(prices[:2])
            else:
                current_price = prices[0]

        title = existing_title
        if not title:
            cleaned = re.sub(r'\d{1,3}(,\d{3})+', '', text)
            cleaned = re.sub(r'\d+%할인', '', cleaned)
            cleaned = re.sub(r'(판매가|정상가|할인|원)', '', cleaned)
            cleaned = re.sub(r'^\d{1,3}\s*', '', cleaned)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            if len(cleaned) > 5:
                title = cleaned

        return title, current_price, original_price, discount

    def _parse_deal_card(self, card, seen_ids: set) -> Optional[NormalizedDeal]:
        """Parse a generic card container."""
        try:
            link_elem = card.select_one("a[href*='/goods/'], a[href*='goodsNo']")
            if not link_elem:
                link_elem = card.select_one("a[href]")
            if not link_elem:
                return None

            href = link_elem.get("href", "")
            id_match = re.search(r"goodsNo=(\d+)", href) or re.search(r"/goods/(\d+)", href)
            if not id_match:
                return None
            external_id = id_match.group(1)

            if external_id in seen_ids:
                return None

            product_url = href
            if not product_url.startswith("http"):
                product_url = f"https://www.ssfshop.com{product_url}"

            brand = None
            brand_elem = card.select_one("[class*='brand']")
            if brand_elem:
                brand = brand_elem.get_text(strip=True)

            title_elem = (
                card.select_one("[class*='name']") or
                card.select_one("[class*='title']") or
                card.select_one("span") or
                link_elem
            )
            title = title_elem.get_text(strip=True) if title_elem else None
            if title and brand and brand not in title:
                title = f"{brand} {title}"
            if not title or len(title) < 3:
                return None

            current_price = None
            for sel in ["[class*='price'] strong", "[class*='sale'] strong", "[class*='price'] em", "strong", "em"]:
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

            original_price = None
            for sel in ["del", "[class*='original']", "[class*='origin']", "s"]:
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
                metadata={"source": "sale"},
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
                metadata={"source": "sale", "shop": self.shop_name},
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
            product_url = f"https://www.ssfshop.com/goods/{external_id}"
            html = await self._safe_scrape(page, product_url, ".product-title, .product-info")
            soup = BeautifulSoup(html, "html.parser")

            brand = None
            brand_elem = soup.select_one(".brand, .brand-name, [class*='brand']")
            if brand_elem:
                brand = brand_elem.get_text(strip=True)

            title_elem = soup.select_one(".product-title, .product-name, h1")
            if not title_elem:
                return None
            product_name = title_elem.get_text(strip=True)
            title = f"{brand} {product_name}".strip() if brand else product_name

            price_elem = soup.select_one(".product-price .sale em, .sale-price em, [class*='price'] strong")
            if not price_elem:
                return None
            current_price = PriceNormalizer.clean_price_string(price_elem.get_text(strip=True))
            if not current_price or current_price <= 0:
                return None

            original_price = None
            original_elem = soup.select_one(".product-price .original del, .original-price del, del")
            if original_elem:
                original_price = PriceNormalizer.clean_price_string(original_elem.get_text(strip=True))

            image_url = None
            img_elem = soup.select_one(".product-img img, .product-image img, img[src*='image']")
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
