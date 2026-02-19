"""Amazon browser scraper adapter.

Scrapes deals from www.amazon.com via Playwright.
Prices are in USD and converted to KRW using CurrencyConverter.

Amazon has the strongest bot detection among all targets.
Anti-bot measures: lowest RPM (3), long random delays 5-10s, immediate abort on CAPTCHA.
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
from app.scrapers.utils.normalizer import (
    PriceNormalizer,
    CategoryClassifier,
    CurrencyConverter,
)


logger = structlog.get_logger()

_DEAL_URLS = [
    "https://www.amazon.com/deals",
    "https://www.amazon.com/gp/goldbox",
    "https://www.amazon.com/gp/bestsellers",
]

_WAIT_SELECTOR = ", ".join([
    "[data-testid*='deal']",
    "[class*='DealCard']",
    "[class*='deal-card']",
    "a[href*='/dp/']",
    "[class*='product']",
    "[class*='ProductCard']",
])

# Amazon CAPTCHA indicators - must be specific to avoid false positives
# "robot" alone triggers on normal pages (meta robots tag), so use full phrases
_CAPTCHA_MARKERS = [
    "enter the characters you see below",
    "type the characters you see",
    "sorry, we just need to make sure you're not a robot",
    "api-services-support@amazon.com",
    "to discuss automated access to amazon data",
]

# USD price pattern: $xx.xx or $x,xxx.xx
_USD_PRICE_PATTERN = re.compile(r'\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)')


class AmazonBrowserAdapter(BaseScraperAdapter):
    """Amazon deal scraper via Playwright browser automation."""

    shop_slug = "amazon"
    shop_name = "아마존"
    RATE_LIMIT_RPM = 3  # Most conservative - Amazon blocks aggressively

    def __init__(self):
        super().__init__()
        self.logger = logger.bind(adapter=self.shop_slug)

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=5, min=10, max=60),
        retry=retry_if_exception_type(Exception),
    )
    async def fetch_deals(self, category: Optional[str] = None) -> List[NormalizedDeal]:
        """Fetch deals from Amazon.com."""
        context = await self._get_browser_context()

        # Warm up: visit homepage first to get cookies (reduces CAPTCHA rate)
        warmup_page = await context.new_page()
        try:
            self.logger.info("amazon_warmup", url="https://www.amazon.com")
            await warmup_page.goto(
                "https://www.amazon.com",
                wait_until="domcontentloaded", timeout=30000,
            )
            await asyncio.sleep(random.uniform(3.0, 5.0))
        except Exception as e:
            self.logger.warning("amazon_warmup_failed", error=str(e))
        finally:
            try:
                await warmup_page.close()
            except Exception:
                pass

        all_deals: List[NormalizedDeal] = []
        seen_ids: set = set()

        for url in _DEAL_URLS:
            page = await context.new_page()
            try:
                self.logger.info("trying_amazon_url", url=url)
                html = await self._safe_scrape(
                    page, url, _WAIT_SELECTOR,
                    scroll=True, wait_seconds=5.0,
                )

                # Check for CAPTCHA - abort entirely if detected
                html_lower = html.lower()
                matched_marker = next(
                    (m for m in _CAPTCHA_MARKERS if m in html_lower), None
                )
                if matched_marker:
                    self.logger.warning(
                        "amazon_captcha_detected", url=url, marker=matched_marker,
                    )
                    break  # Don't try more URLs - we're flagged

                deals = self._parse_deals_from_html(html, seen_ids)
                if deals:
                    all_deals.extend(deals)
                    self.logger.info("amazon_deals_found", url=url, count=len(deals))

                # Long random delay - Amazon is very sensitive
                await asyncio.sleep(random.uniform(5.0, 10.0))

                if len(all_deals) >= 40:
                    break
            except Exception as e:
                self.logger.warning("amazon_url_failed", url=url, error=str(e))
            finally:
                try:
                    await page.close()
                except Exception:
                    pass

        self.logger.info("fetched_amazon_deals_total", count=len(all_deals))
        return all_deals

    def _parse_deals_from_html(self, html: str, seen_ids: set) -> List[NormalizedDeal]:
        """Parse deals from Amazon HTML."""
        soup = BeautifulSoup(html, "html.parser")
        deals = []

        # Strategy 1: Deal cards on deals page
        deal_cards = soup.select(
            "[data-testid*='deal'], [class*='DealCard'], "
            "[class*='deal-card'], [class*='dealCard']"
        )
        self.logger.info("amazon_deal_cards_found", count=len(deal_cards))

        for card in deal_cards:
            deal = self._parse_deal_card(card, seen_ids)
            if deal:
                deals.append(deal)
                seen_ids.add(deal.product.external_id)

        # Strategy 2: Grid items (bestsellers, category pages)
        # Amazon wraps each product in a div with role or data-asin or zg-item
        grid_items = soup.select(
            "[data-asin], [id*='gridItemRoot'], .zg-grid-general-faceout, "
            ".s-result-item, [data-component-type='s-search-result']"
        )
        self.logger.info("amazon_grid_items_found", count=len(grid_items))

        for item in grid_items:
            deal = self._parse_grid_item(item, seen_ids)
            if deal:
                deals.append(deal)
                seen_ids.add(deal.product.external_id)

        if deals:
            return deals

        # Strategy 3: Fallback — walk up from /dp/ links
        dp_links = soup.select("a[href*='/dp/']")
        self.logger.info("amazon_dp_links_found", count=len(dp_links))

        for link in dp_links:
            deal = self._parse_dp_link(link, seen_ids)
            if deal:
                deals.append(deal)
                seen_ids.add(deal.product.external_id)

        return deals

    def _extract_asin(self, href: str) -> Optional[str]:
        """Extract ASIN (10-char alphanumeric ID) from Amazon URL."""
        match = re.search(r'/dp/([A-Z0-9]{10})', href)
        if match:
            return match.group(1)
        match = re.search(r'/gp/product/([A-Z0-9]{10})', href)
        if match:
            return match.group(1)
        return None

    def _parse_usd_price(self, text: str) -> Optional[Decimal]:
        """Parse USD price from text like '$29.99' or '$1,299.00'."""
        match = _USD_PRICE_PATTERN.search(text)
        if match:
            price_str = match.group(1).replace(",", "")
            try:
                return Decimal(price_str)
            except Exception:
                return None
        return None

    def _extract_price_from_container(self, container) -> Optional[Decimal]:
        """Extract USD price from an Amazon container using multiple strategies."""
        # Strategy 1: a-offscreen spans (most reliable, used for screen readers)
        for elem in container.select(".a-offscreen"):
            price = self._parse_usd_price(elem.get_text(strip=True))
            if price and price > Decimal("0.50"):
                return price

        # Strategy 2: a-price-whole + a-price-fraction
        whole_elem = container.select_one(".a-price-whole")
        frac_elem = container.select_one(".a-price-fraction")
        if whole_elem:
            whole = whole_elem.get_text(strip=True).rstrip(".")
            frac = frac_elem.get_text(strip=True) if frac_elem else "00"
            try:
                return Decimal(f"{whole.replace(',', '')}.{frac}")
            except Exception:
                pass

        # Strategy 3: $xx.xx pattern in text
        text = container.get_text()
        price = self._parse_usd_price(text)
        if price and price > Decimal("0.50"):
            return price

        return None

    def _extract_title_from_container(self, container, link_elem=None) -> Optional[str]:
        """Extract product title from an Amazon container."""
        # Try common Amazon title selectors
        for sel in [
            ".a-link-normal .a-text-normal",
            "[class*='_title'] a", "[class*='title'] a",
            "h2 a", "h2 span", "h2",
            "[class*='p13n-sc-truncate']",
            ".a-size-base-plus", ".a-size-medium",
            "[class*='_title']", "[class*='title']",
            "a[title]",
        ]:
            elem = container.select_one(sel)
            if elem:
                t = elem.get("title") or elem.get_text(strip=True)
                if t and len(t) > 5 and not re.match(r'^[\$\d,.\s%]+$', t):
                    return t[:200]

        # Fallback: link text
        if link_elem:
            t = link_elem.get("title") or link_elem.get_text(strip=True)
            if t and len(t) > 5 and not re.match(r'^[\$\d,.\s%]+$', t):
                return t[:200]

        return None

    def _parse_grid_item(self, item, seen_ids: set) -> Optional[NormalizedDeal]:
        """Parse a deal from an Amazon grid/list item (bestsellers, search results)."""
        try:
            # ASIN from data attribute or from link
            asin = item.get("data-asin")
            if not asin:
                link = item.select_one("a[href*='/dp/']") or item.select_one("a[href*='/gp/product/']")
                if link:
                    asin = self._extract_asin(link.get("href", ""))
            if not asin or asin in seen_ids:
                return None

            product_url = f"https://www.amazon.com/dp/{asin}"

            title = self._extract_title_from_container(item)
            if not title:
                return None

            price_usd = self._extract_price_from_container(item)
            if not price_usd:
                return None

            current_price = CurrencyConverter.to_krw(price_usd, "USD")

            # Image
            image_url = None
            img = item.select_one("img.s-image, img[data-image-index], img")
            if img:
                image_url = img.get("src") or img.get("data-src")
                if image_url and not image_url.startswith("http"):
                    image_url = None

            category_hint = CategoryClassifier.classify(title)

            product = NormalizedProduct(
                external_id=asin,
                title=title,
                current_price=current_price,
                product_url=product_url,
                currency="KRW",
                image_url=image_url,
                category_hint=category_hint,
                metadata={"source": "amazon_grid", "price_usd": float(price_usd)},
            )

            return NormalizedDeal(
                product=product,
                deal_price=current_price,
                title=title,
                deal_url=product_url,
                deal_type="flash_sale",
                image_url=image_url,
                metadata={
                    "source": "amazon_grid",
                    "price_usd": float(price_usd),
                    "shop": self.shop_name,
                },
            )

        except Exception as e:
            self.logger.debug("parse_amazon_grid_item_failed", error=str(e))
            return None

    def _parse_deal_card(self, card, seen_ids: set) -> Optional[NormalizedDeal]:
        """Parse a deal from an Amazon deal card element."""
        try:
            # Find ASIN link
            link = card.select_one("a[href*='/dp/']") or card.select_one("a[href*='/gp/product/']")
            if not link:
                return None

            href = link.get("href", "")
            asin = self._extract_asin(href)
            if not asin or asin in seen_ids:
                return None

            product_url = f"https://www.amazon.com/dp/{asin}"

            # Title
            title = None
            for sel in [
                "[class*='title']", "[class*='Title']", "[class*='name']",
                "[class*='truncate']", "[aria-label]",
            ]:
                elem = card.select_one(sel)
                if elem:
                    t = elem.get("aria-label") or elem.get_text(strip=True)
                    if t and len(t) > 5 and not re.match(r'^[\$\d,.\s%]+$', t):
                        title = t
                        break

            if not title:
                link_text = link.get_text(strip=True)
                if link_text and len(link_text) > 5:
                    title = link_text

            if not title:
                return None

            # Prices (USD)
            card_text = card.get_text()
            usd_prices = _USD_PRICE_PATTERN.findall(card_text)
            if not usd_prices:
                return None

            parsed_prices = []
            for p in usd_prices:
                try:
                    val = Decimal(p.replace(",", ""))
                    if val > 0:
                        parsed_prices.append(val)
                except Exception:
                    continue

            if not parsed_prices:
                return None

            parsed_prices.sort()
            deal_price_usd = parsed_prices[0]
            original_price_usd = parsed_prices[-1] if len(parsed_prices) > 1 and parsed_prices[-1] > deal_price_usd else None

            # Convert to KRW
            current_price = CurrencyConverter.to_krw(deal_price_usd, "USD")
            original_price = CurrencyConverter.to_krw(original_price_usd, "USD") if original_price_usd else None

            # Discount percentage
            discount_pct = None
            pct_match = re.search(r'(\d{1,2})\s*%\s*off', card_text, re.IGNORECASE)
            if pct_match:
                pct_val = int(pct_match.group(1))
                if 1 <= pct_val <= 99:
                    discount_pct = Decimal(str(pct_val))
            elif original_price and original_price > current_price:
                discount_pct = ((original_price - current_price) / original_price * 100).quantize(Decimal("1"))

            # Image
            image_url = None
            img = card.select_one("img")
            if img:
                image_url = img.get("src") or img.get("data-src")
                if image_url and not image_url.startswith("http"):
                    image_url = None

            title = title[:200].strip()
            category_hint = CategoryClassifier.classify(title)

            product = NormalizedProduct(
                external_id=asin,
                title=title,
                current_price=current_price,
                product_url=product_url,
                original_price=original_price,
                currency="KRW",
                image_url=image_url,
                category_hint=category_hint,
                metadata={
                    "source": "amazon_deals",
                    "price_usd": float(deal_price_usd),
                    "original_price_usd": float(original_price_usd) if original_price_usd else None,
                },
            )

            return NormalizedDeal(
                product=product,
                deal_price=current_price,
                original_price=original_price,
                discount_percentage=discount_pct,
                title=title,
                deal_url=product_url,
                deal_type="flash_sale",
                image_url=image_url,
                metadata={
                    "source": "amazon_deals",
                    "price_usd": float(deal_price_usd),
                    "shop": self.shop_name,
                },
            )

        except Exception as e:
            self.logger.debug("parse_amazon_deal_card_failed", error=str(e))
            return None

    def _parse_dp_link(self, link_elem, seen_ids: set) -> Optional[NormalizedDeal]:
        """Parse a deal from an Amazon /dp/ link."""
        try:
            href = link_elem.get("href", "")
            asin = self._extract_asin(href)
            if not asin or asin in seen_ids:
                return None

            product_url = f"https://www.amazon.com/dp/{asin}"

            # Walk up to find container
            container = link_elem
            title = None
            current_price = None
            original_price = None
            image_url = None

            for _ in range(5):
                if container.parent is None:
                    break
                container = container.parent

                # Look for USD prices
                container_text = container.get_text()
                usd_prices = _USD_PRICE_PATTERN.findall(container_text)
                if not usd_prices:
                    continue

                # Title
                for sel in ["[class*='title']", "[class*='name']", "h2", "span[class*='a-text']"]:
                    elem = container.select_one(sel)
                    if elem:
                        t = elem.get_text(strip=True)
                        if t and len(t) > 5 and not re.match(r'^[\$\d,.\s%]+$', t):
                            title = t
                            break

                if not title:
                    link_text = link_elem.get_text(strip=True)
                    if link_text and len(link_text) > 5:
                        title = link_text

                # Prices
                parsed_prices = []
                for p in usd_prices:
                    try:
                        val = Decimal(p.replace(",", ""))
                        if val > 0:
                            parsed_prices.append(val)
                    except Exception:
                        continue

                if parsed_prices:
                    parsed_prices.sort()
                    deal_usd = parsed_prices[0]
                    current_price = CurrencyConverter.to_krw(deal_usd, "USD")
                    if len(parsed_prices) > 1 and parsed_prices[-1] > deal_usd:
                        original_price = CurrencyConverter.to_krw(parsed_prices[-1], "USD")

                # Image
                img = container.select_one("img")
                if img:
                    image_url = img.get("src") or img.get("data-src")
                    if image_url and not image_url.startswith("http"):
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
                external_id=asin,
                title=title,
                current_price=current_price,
                product_url=product_url,
                original_price=original_price,
                currency="KRW",
                image_url=image_url,
                category_hint=category_hint,
                metadata={"source": "amazon_browse"},
            )

            return NormalizedDeal(
                product=product,
                deal_price=current_price,
                original_price=original_price,
                discount_percentage=discount_pct,
                title=title,
                deal_url=product_url,
                deal_type="flash_sale",
                image_url=image_url,
                metadata={"source": "amazon_browse", "shop": self.shop_name},
            )

        except Exception as e:
            self.logger.debug("parse_amazon_dp_link_failed", error=str(e))
            return None

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=3, min=5, max=30),
        retry=retry_if_exception_type(Exception),
    )
    async def fetch_product_details(self, external_id: str) -> Optional[NormalizedProduct]:
        """Fetch detailed product info from Amazon product page."""
        context = await self._get_browser_context()
        page = await context.new_page()

        try:
            url = f"https://www.amazon.com/dp/{external_id}"
            html = await self._safe_scrape(page, url, "#productTitle, h1")

            html_lower = html.lower()
            if any(marker in html_lower for marker in _CAPTCHA_MARKERS):
                self.logger.warning("amazon_captcha_on_product", external_id=external_id)
                return None

            soup = BeautifulSoup(html, "html.parser")

            # Title
            title_elem = soup.select_one("#productTitle") or soup.select_one("h1")
            if not title_elem:
                return None
            title = title_elem.get_text(strip=True)

            # Price
            price_text = None
            for sel in [
                "#priceblock_dealprice", "#priceblock_ourprice",
                ".a-price .a-offscreen", "[class*='priceToPay']",
                "[class*='price'] .a-offscreen",
            ]:
                elem = soup.select_one(sel)
                if elem:
                    price_text = elem.get_text(strip=True)
                    break

            if not price_text:
                return None

            price_usd = self._parse_usd_price(price_text)
            if not price_usd or price_usd <= 0:
                return None

            current_price = CurrencyConverter.to_krw(price_usd, "USD")

            # Original price
            original_price = None
            orig_elem = soup.select_one(
                ".a-text-price .a-offscreen, [class*='basisPrice'] .a-offscreen"
            )
            if orig_elem:
                orig_usd = self._parse_usd_price(orig_elem.get_text(strip=True))
                if orig_usd and orig_usd > price_usd:
                    original_price = CurrencyConverter.to_krw(orig_usd, "USD")

            # Image
            image_url = None
            img = soup.select_one("#landingImage, #imgBlkFront, [class*='image'] img")
            if img:
                image_url = img.get("src") or img.get("data-src")
                if image_url and not image_url.startswith("http"):
                    image_url = None

            # Brand
            brand = None
            brand_elem = soup.select_one("#bylineInfo, [class*='brand']")
            if brand_elem:
                brand = brand_elem.get_text(strip=True).replace("Visit the ", "").replace(" Store", "")

            return NormalizedProduct(
                external_id=external_id,
                title=title,
                current_price=current_price,
                product_url=url,
                original_price=original_price,
                currency="KRW",
                image_url=image_url,
                brand=brand,
                category_hint=CategoryClassifier.classify(title),
                metadata={
                    "source": "amazon_product_page",
                    "price_usd": float(price_usd),
                    "shop": self.shop_name,
                },
            )

        except Exception as e:
            self.logger.error("fetch_product_details_failed", external_id=external_id, error=str(e))
            return None
        finally:
            await page.close()
