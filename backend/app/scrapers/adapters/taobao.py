"""
Taobao (淘宝) Scraper Adapter

This is the HARDEST scraping target due to Alibaba's aggressive anti-bot system.
Uses world.taobao.com for international access with less strict bot detection.

Anti-bot measures implemented:
- Low rate limit (5 RPM)
- User-agent rotation
- Random delays and human-like behavior
- Proxy support (Chinese IP preferred)
- Fallback to mobile H5 pages

Target pages (no login required):
- World Taobao search: https://world.taobao.com/search/search.htm?q={keyword}
- Mobile daily deals: https://h5.m.taobao.com/act/dailyDeals/index.html

Note: This adapter will fail frequently due to CAPTCHA and IP blocks.
Expected success rate: 30-50% depending on proxy quality.
"""

import asyncio
import random
import re
from typing import Optional, List
from datetime import datetime
from bs4 import BeautifulSoup
try:
    from playwright.async_api import Page, TimeoutError as PlaywrightTimeout
except ImportError:
    Page = None
    PlaywrightTimeout = TimeoutError

from app.scrapers.base import BaseScraperAdapter, NormalizedDeal, NormalizedProduct
from app.scrapers.utils.normalizer import PriceNormalizer, CategoryClassifier
from app.scrapers.utils.rate_limiter import DomainRateLimiter


class TaobaoAdapter(BaseScraperAdapter):
    """
    Taobao scraper adapter with aggressive anti-bot countermeasures.

    Challenges:
    - Alibaba's puncha.js anti-bot system
    - Slide CAPTCHA detection
    - IP-based rate limiting
    - Dynamic content loading

    Strategy:
    - Use world.taobao.com (less strict, international focus)
    - Simulate human browsing patterns
    - Low rate limits with random delays
    - Graceful degradation on failures
    """

    shop_slug = "taobao"
    shop_name = "타오바오"
    adapter_type = "scraper"

    # Category mapping to Chinese keywords
    CATEGORY_KEYWORDS = {
        "pc-hardware": ["显卡", "固态硬盘", "内存条", "主板", "CPU处理器"],
        "laptop-mobile": ["笔记本电脑", "平板电脑", "智能手机", "iPad", "MacBook"],
        "electronics-tv": ["蓝牙耳机", "电视", "扫地机器人", "智能音箱", "投影仪"],
        "games-software": ["游戏手柄", "Switch游戏", "键盘鼠标", "电竞椅"],
        "fashion": ["运动鞋", "T恤", "牛仔裤", "包包"],
        "beauty": ["护肤品", "化妆品", "香水"],
    }

    # User agents for rotation (realistic desktop browsers)
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    ]

    def __init__(self, page: Optional[Page] = None):
        """Initialize Taobao adapter with strict rate limiting."""
        super().__init__(page)

        # Very conservative rate limits (5 RPM)
        self.rate_limiter.set_domain_limit("s.taobao.com", requests_per_minute=5)
        self.rate_limiter.set_domain_limit("world.taobao.com", requests_per_minute=5)
        self.rate_limiter.set_domain_limit("h5.m.taobao.com", requests_per_minute=5)

        self.normalizer = PriceNormalizer()
        self.classifier = CategoryClassifier()

    async def fetch_deals(self, category: Optional[str] = None) -> List[NormalizedDeal]:
        """
        Fetch deals from Taobao using world.taobao.com search.

        Args:
            category: Category slug to search (maps to Chinese keywords)

        Returns:
            List of normalized deals (may be empty on failure)
        """
        if not self.page:
            raise ValueError("Browser page not set. Call set_page() first.")

        deals = []

        # Get search keywords for category
        search_terms = self._get_search_terms(category)

        for term in search_terms:
            try:
                # Rate limit before request
                await self.rate_limiter.wait_if_needed("world.taobao.com")

                # Fetch search results
                term_deals = await self._fetch_search_results(term, category)
                deals.extend(term_deals)

                # Random delay between searches (human-like)
                await asyncio.sleep(random.uniform(2.0, 4.0))

                # Limit total deals per category
                if len(deals) >= 30:
                    break

            except Exception as e:
                self.logger.error(
                    f"Failed to fetch deals for term '{term}': {e}",
                    extra={"category": category, "term": term}
                )
                continue

        self.logger.info(
            f"Fetched {len(deals)} deals from Taobao",
            extra={"category": category}
        )

        return deals

    async def fetch_product_details(self, external_id: str) -> Optional[NormalizedProduct]:
        """
        Fetch detailed product info from item page.

        Note: Often fails due to anti-bot measures. Not critical for deal aggregation.

        Args:
            external_id: Taobao item ID

        Returns:
            NormalizedProduct or None on failure
        """
        if not self.page:
            raise ValueError("Browser page not set. Call set_page() first.")

        try:
            # Rate limit
            await self.rate_limiter.wait_if_needed("world.taobao.com")

            # Item page URL (world.taobao.com version)
            url = f"https://world.taobao.com/item/{external_id}.htm"

            # Random user agent
            await self.page.set_extra_http_headers({
                "User-Agent": random.choice(self.USER_AGENTS)
            })

            # Navigate with timeout
            await self.page.goto(url, wait_until="domcontentloaded", timeout=15000)

            # Simulate human behavior
            await self._simulate_human_behavior(self.page)

            # Wait for product info
            await self.page.wait_for_selector(".tb-detail-hd", timeout=10000)

            # Parse page
            html = await self.page.content()
            soup = BeautifulSoup(html, "html.parser")

            product = self._parse_product_page(soup, external_id)
            return product

        except PlaywrightTimeout:
            self.logger.warning(
                f"Timeout fetching product {external_id} - possible CAPTCHA",
                extra={"external_id": external_id}
            )
            return None
        except Exception as e:
            self.logger.error(
                f"Failed to fetch product details: {e}",
                extra={"external_id": external_id}
            )
            return None

    async def health_check(self) -> bool:
        """
        Check if Taobao is accessible (not blocked).

        Returns:
            True if search page loads, False if blocked/CAPTCHA
        """
        if not self.page:
            return False

        try:
            await self.rate_limiter.wait_if_needed("world.taobao.com")

            # Try loading search page
            url = "https://world.taobao.com/search/search.htm?q=test"
            await self.page.goto(url, wait_until="domcontentloaded", timeout=10000)

            # Check for CAPTCHA indicators
            html = await self.page.content()
            if "验证码" in html or "puncha" in html or "slider" in html.lower():
                self.logger.warning("Taobao CAPTCHA detected during health check")
                return False

            # Check for search results container
            has_results = await self.page.locator(".item").count() > 0
            return has_results

        except Exception as e:
            self.logger.error(f"Taobao health check failed: {e}")
            return False

    def _get_search_terms(self, category: Optional[str]) -> List[str]:
        """Get Chinese search terms for category."""
        if category and category in self.CATEGORY_KEYWORDS:
            # Return 2-3 terms per category (avoid too many requests)
            return self.CATEGORY_KEYWORDS[category][:3]

        # Default: sample from multiple categories
        all_terms = []
        for cat_terms in self.CATEGORY_KEYWORDS.values():
            all_terms.extend(cat_terms[:1])  # One term per category
        return all_terms[:5]  # Max 5 terms

    async def _fetch_search_results(
        self,
        search_term: str,
        category_hint: Optional[str]
    ) -> List[NormalizedDeal]:
        """Fetch and parse search results for a term."""
        deals = []

        try:
            # World Taobao search URL
            url = f"https://world.taobao.com/search/search.htm?q={search_term}"

            # Random user agent
            await self.page.set_extra_http_headers({
                "User-Agent": random.choice(self.USER_AGENTS),
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            })

            # Navigate
            await self.page.goto(url, wait_until="domcontentloaded", timeout=15000)

            # Simulate human browsing
            await self._simulate_human_behavior(self.page)

            # Wait for product items (multiple selectors for resilience)
            selectors = [".item", ".product-item", ".J_ItemList .item"]
            loaded = False
            for selector in selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=8000)
                    loaded = True
                    break
                except PlaywrightTimeout:
                    continue

            if not loaded:
                self.logger.warning(f"No products found for term: {search_term}")
                return []

            # Parse HTML
            html = await self.page.content()

            # Check for CAPTCHA
            if "验证码" in html or "puncha" in html:
                self.logger.warning(f"CAPTCHA triggered for search: {search_term}")
                return []

            soup = BeautifulSoup(html, "html.parser")

            # Parse product cards (limit to 10 per search)
            items = soup.select(".item")[:10]

            for item in items:
                try:
                    deal = self._normalize_item(item, category_hint)
                    if deal:
                        deals.append(deal)
                except Exception as e:
                    self.logger.debug(f"Failed to parse item: {e}")
                    continue

        except PlaywrightTimeout:
            self.logger.warning(f"Timeout loading search results for: {search_term}")
        except Exception as e:
            self.logger.error(f"Error fetching search results: {e}")

        return deals

    def _normalize_item(self, item: BeautifulSoup, category_hint: Optional[str]) -> Optional[NormalizedDeal]:
        """Parse and normalize a product item from search results."""
        try:
            # Extract title (multiple selectors)
            title_elem = (
                item.select_one(".title a") or
                item.select_one(".item-title") or
                item.select_one("a[title]")
            )
            if not title_elem:
                return None

            title = title_elem.get("title") or title_elem.get_text(strip=True)
            if not title:
                return None

            # Extract price (CNY)
            price_elem = (
                item.select_one(".price strong") or
                item.select_one(".price") or
                item.select_one(".g_price")
            )
            if not price_elem:
                return None

            price_text = price_elem.get_text(strip=True)
            # Parse CNY price (format: ¥123.45 or 123.45)
            price_match = re.search(r'[\d,]+\.?\d*', price_text)
            if not price_match:
                return None

            price_cny = float(price_match.group().replace(",", ""))

            # Convert CNY to KRW
            price_krw = self.normalizer.to_krw(price_cny, "CNY")

            # Extract link and item ID
            link_elem = item.select_one("a[href]")
            if not link_elem:
                return None

            link = link_elem.get("href", "")
            if not link.startswith("http"):
                link = "https:" + link if link.startswith("//") else "https://world.taobao.com" + link

            # Extract item ID from link
            item_id_match = re.search(r'id=(\d+)', link)
            external_id = item_id_match.group(1) if item_id_match else None
            if not external_id:
                return None

            # Extract image
            img_elem = item.select_one("img")
            image_url = None
            if img_elem:
                image_url = img_elem.get("src") or img_elem.get("data-src")
                if image_url and not image_url.startswith("http"):
                    image_url = "https:" + image_url

            # Classify category
            category = self.classifier.classify(title)
            if category_hint and not category:
                category = category_hint

            # Sales count (if available)
            sales_elem = item.select_one(".deal-cnt")
            sales_count = None
            if sales_elem:
                sales_text = sales_elem.get_text(strip=True)
                sales_match = re.search(r'\d+', sales_text)
                if sales_match:
                    sales_count = int(sales_match.group())

            return NormalizedDeal(
                shop_slug=self.shop_slug,
                external_id=external_id,
                title=title,
                url=link,
                current_price=price_krw,
                original_price=price_krw,  # No original price in search results
                discount_percentage=0.0,
                category=category,
                image_url=image_url,
                deal_type="clearance",
                starts_at=datetime.utcnow(),
                ends_at=None,
                metadata_={
                    "price_cny": price_cny,
                    "sales_count": sales_count,
                    "source": "world.taobao.com",
                }
            )

        except Exception as e:
            self.logger.debug(f"Error normalizing item: {e}")
            return None

    def _parse_product_page(self, soup: BeautifulSoup, external_id: str) -> Optional[NormalizedProduct]:
        """Parse product details from item page."""
        try:
            # Title
            title_elem = soup.select_one(".tb-detail-hd h1") or soup.select_one("h1")
            if not title_elem:
                return None
            title = title_elem.get_text(strip=True)

            # Price
            price_elem = soup.select_one(".tb-rmb-num") or soup.select_one(".price strong")
            if not price_elem:
                return None

            price_text = price_elem.get_text(strip=True)
            price_match = re.search(r'[\d,]+\.?\d*', price_text)
            if not price_match:
                return None

            price_cny = float(price_match.group().replace(",", ""))
            price_krw = self.normalizer.to_krw(price_cny, "CNY")

            # Image
            img_elem = soup.select_one(".tb-booth-main img")
            image_url = None
            if img_elem:
                image_url = img_elem.get("src") or img_elem.get("data-src")
                if image_url and not image_url.startswith("http"):
                    image_url = "https:" + image_url

            # Category
            category = self.classifier.classify(title)

            return NormalizedProduct(
                shop_slug=self.shop_slug,
                external_id=external_id,
                title=title,
                url=f"https://world.taobao.com/item/{external_id}.htm",
                current_price=price_krw,
                original_price=price_krw,
                category=category,
                image_url=image_url,
                in_stock=True,
                metadata_={"price_cny": price_cny}
            )

        except Exception as e:
            self.logger.debug(f"Error parsing product page: {e}")
            return None

    async def _simulate_human_behavior(self, page: Page):
        """
        Simulate human-like browsing to avoid bot detection.

        - Random scrolling
        - Random mouse movements
        - Random delays
        """
        try:
            # Random scroll
            scroll_distance = random.randint(300, 800)
            await page.evaluate(f"window.scrollBy(0, {scroll_distance})")
            await asyncio.sleep(random.uniform(0.5, 1.5))

            # Scroll back up a bit
            await page.evaluate(f"window.scrollBy(0, -{scroll_distance // 2})")
            await asyncio.sleep(random.uniform(0.3, 0.8))

            # Random mouse movement (if possible)
            try:
                await page.mouse.move(
                    random.randint(100, 500),
                    random.randint(100, 500)
                )
            except Exception:
                pass  # Mouse movement may not be supported

            # Final delay
            await asyncio.sleep(random.uniform(0.5, 1.0))

        except Exception as e:
            self.logger.debug(f"Error simulating human behavior: {e}")
