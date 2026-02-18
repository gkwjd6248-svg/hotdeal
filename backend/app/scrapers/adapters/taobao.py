"""Taobao (淘宝) scraper adapter.

Scrapes deals from world.taobao.com for international access.
Hardest scraping target due to Alibaba's aggressive anti-bot system.

Anti-bot measures: low RPM, random delays, human-like scrolling.
Expected success rate: 30-50% depending on proxy quality.
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

# Search keywords per category (Chinese)
_CATEGORY_KEYWORDS = {
    "pc-hardware": ["显卡", "固态硬盘", "内存条"],
    "laptop-mobile": ["笔记本电脑", "平板电脑", "智能手机"],
    "electronics-tv": ["蓝牙耳机", "电视", "扫地机器人"],
    "games-software": ["游戏手柄", "键盘鼠标"],
    "fashion": ["运动鞋", "T恤"],
    "beauty": ["护肤品", "化妆品"],
}

# Default terms when no category specified
_DEFAULT_TERMS = ["数码好物", "电子产品特价", "今日特价"]

_WAIT_SELECTOR = ", ".join([
    ".item",
    ".product-item",
    "[class*='item']",
    "[class*='product']",
])

# CNY to KRW rough rate (updated periodically by CurrencyConverter)
_CNY_TO_KRW_FALLBACK = Decimal("190")


class TaobaoAdapter(BaseScraperAdapter):
    """Taobao deal scraper adapter with anti-bot countermeasures."""

    shop_slug = "taobao"
    shop_name = "타오바오"
    RATE_LIMIT_RPM = 5  # Very conservative

    def __init__(self):
        super().__init__()
        self.logger = logger.bind(adapter=self.shop_slug)

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=3, min=5, max=30),
        retry=retry_if_exception_type(Exception),
    )
    async def fetch_deals(self, category: Optional[str] = None) -> List[NormalizedDeal]:
        """Fetch deals from Taobao via world.taobao.com search."""
        context = await self._get_browser_context()

        all_deals: List[NormalizedDeal] = []
        seen_ids: set = set()

        search_terms = self._get_search_terms(category)

        for term in search_terms:
            page = await context.new_page()
            try:
                deals = await self._search_and_parse(page, term, category, seen_ids)
                if deals:
                    all_deals.extend(deals)
                    self.logger.info("taobao_deals_found", term=term, count=len(deals))

                # Random delay between searches
                await asyncio.sleep(random.uniform(2.0, 4.0))

                if len(all_deals) >= 30:
                    break
            except Exception as e:
                self.logger.warning("taobao_search_failed", term=term, error=str(e))
            finally:
                try:
                    await page.close()
                except Exception:
                    pass

        self.logger.info("fetched_taobao_deals_total", count=len(all_deals))
        return all_deals

    def _get_search_terms(self, category: Optional[str]) -> List[str]:
        """Get Chinese search terms for category."""
        if category and category in _CATEGORY_KEYWORDS:
            return _CATEGORY_KEYWORDS[category][:3]
        return _DEFAULT_TERMS

    async def _search_and_parse(
        self, page: Page, term: str, category_hint: Optional[str], seen_ids: set,
    ) -> List[NormalizedDeal]:
        """Search world.taobao.com and parse results."""
        url = f"https://world.taobao.com/search/search.htm?q={term}"
        self.logger.info("taobao_searching", term=term, url=url)

        html = await self._safe_scrape(
            page, url, _WAIT_SELECTOR,
            scroll=True, wait_seconds=3.0,
        )

        # Check for CAPTCHA
        if "验证码" in html or "puncha" in html:
            self.logger.warning("taobao_captcha_detected", term=term)
            return []

        soup = BeautifulSoup(html, "html.parser")
        deals = []

        # Find product items
        items = soup.select(".item, .product-item, [class*='ContentItem']")[:15]
        self.logger.info("taobao_items_found", count=len(items))

        for item in items:
            deal = self._parse_item(item, category_hint, seen_ids)
            if deal:
                deals.append(deal)
                seen_ids.add(deal.product.external_id)

        return deals

    def _parse_item(self, item, category_hint: Optional[str], seen_ids: set) -> Optional[NormalizedDeal]:
        """Parse a product item from search results."""
        try:
            # Title
            title_elem = (
                item.select_one(".title a") or
                item.select_one("[class*='title']") or
                item.select_one("a[title]")
            )
            if not title_elem:
                return None

            title = title_elem.get("title") or title_elem.get_text(strip=True)
            if not title or len(title) < 3:
                return None

            # Price (CNY)
            price_elem = (
                item.select_one(".price strong") or
                item.select_one(".price") or
                item.select_one("[class*='price']")
            )
            if not price_elem:
                return None

            price_text = price_elem.get_text(strip=True)
            price_match = re.search(r'[\d,]+\.?\d*', price_text)
            if not price_match:
                return None

            price_cny = Decimal(price_match.group().replace(",", ""))
            if price_cny <= 0:
                return None

            # Convert CNY to KRW
            current_price = price_cny * _CNY_TO_KRW_FALLBACK

            # Link and item ID
            link_elem = item.select_one("a[href]")
            if not link_elem:
                return None

            link = link_elem.get("href", "")
            if link.startswith("//"):
                link = f"https:{link}"
            elif not link.startswith("http"):
                link = f"https://world.taobao.com{link}"

            item_id_match = re.search(r'id=(\d+)', link)
            if not item_id_match:
                return None
            external_id = item_id_match.group(1)

            if external_id in seen_ids:
                return None

            # Image
            image_url = None
            img_elem = item.select_one("img")
            if img_elem:
                image_url = img_elem.get("src") or img_elem.get("data-src")
                if image_url and image_url.startswith("//"):
                    image_url = f"https:{image_url}"
                elif image_url and not image_url.startswith("http"):
                    image_url = None

            category = CategoryClassifier.classify(title)
            if not category and category_hint:
                category = category_hint

            product = NormalizedProduct(
                external_id=external_id,
                title=title,
                current_price=current_price,
                product_url=link,
                currency="KRW",
                image_url=image_url,
                category_hint=category,
                metadata={"price_cny": float(price_cny), "source": "world.taobao.com"},
            )

            return NormalizedDeal(
                product=product,
                deal_price=current_price,
                title=title,
                deal_url=link,
                deal_type="clearance",
                image_url=image_url,
                metadata={"price_cny": float(price_cny), "shop": self.shop_name},
            )

        except Exception as e:
            self.logger.debug("parse_taobao_item_failed", error=str(e))
            return None

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=2, min=3, max=15),
        retry=retry_if_exception_type(Exception),
    )
    async def fetch_product_details(self, external_id: str) -> Optional[NormalizedProduct]:
        """Fetch detailed product info from Taobao item page."""
        context = await self._get_browser_context()
        page = await context.new_page()

        try:
            url = f"https://world.taobao.com/item/{external_id}.htm"
            html = await self._safe_scrape(page, url, ".tb-detail-hd, h1, [class*='title']")
            soup = BeautifulSoup(html, "html.parser")

            # Check for CAPTCHA
            if "验证码" in html or "puncha" in html:
                self.logger.warning("taobao_captcha_on_product", external_id=external_id)
                return None

            title_elem = soup.select_one(".tb-detail-hd h1") or soup.select_one("h1")
            if not title_elem:
                return None
            title = title_elem.get_text(strip=True)

            price_elem = soup.select_one(".tb-rmb-num") or soup.select_one(".price strong")
            if not price_elem:
                return None

            price_text = price_elem.get_text(strip=True)
            price_match = re.search(r'[\d,]+\.?\d*', price_text)
            if not price_match:
                return None

            price_cny = Decimal(price_match.group().replace(",", ""))
            current_price = price_cny * _CNY_TO_KRW_FALLBACK

            image_url = None
            img_elem = soup.select_one(".tb-booth-main img, img[src*='taobaocdn']")
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
                product_url=url,
                currency="KRW",
                image_url=image_url,
                category_hint=CategoryClassifier.classify(title),
                metadata={"price_cny": float(price_cny), "shop": self.shop_name},
            )

        except Exception as e:
            self.logger.error("fetch_product_details_failed", external_id=external_id, error=str(e))
            return None
        finally:
            await page.close()
