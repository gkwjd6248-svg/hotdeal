"""Playwright browser lifecycle manager with anti-detection.

Provides shared browser instances with context pooling,
proxy rotation, and stealth configuration.
"""

import asyncio
from typing import Optional, Dict

import structlog
from playwright.async_api import async_playwright, Browser, BrowserContext, Playwright

from app.scrapers.utils.user_agents import get_random_user_agent
from app.scrapers.utils.proxy_manager import ProxyManager, NoProxyManager
from app.config import settings

logger = structlog.get_logger()


class BrowserManager:
    """Manages Playwright browser lifecycle with anti-detection features.

    Creates and pools browser contexts with:
    - User-agent rotation per context
    - Optional proxy rotation
    - Stealth JS injection to bypass bot detection
    - Resource blocking (images/fonts) for faster scraping
    """

    def __init__(
        self,
        headless: bool = True,
        proxy_manager: Optional[ProxyManager] = None,
        block_resources: bool = True,
    ):
        self._headless = headless
        self._proxy_manager = proxy_manager or NoProxyManager()
        self._block_resources = block_resources
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._lock = asyncio.Lock()
        self._contexts: Dict[str, BrowserContext] = {}

    async def start(self) -> None:
        """Launch the browser. Call once at application startup."""
        async with self._lock:
            if self._browser:
                return
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self._headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            )
            logger.info("browser_started", headless=self._headless)

    async def stop(self) -> None:
        """Close all contexts and the browser."""
        async with self._lock:
            for name, ctx in self._contexts.items():
                try:
                    await ctx.close()
                except Exception:
                    pass
            self._contexts.clear()

            if self._browser:
                await self._browser.close()
                self._browser = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
            logger.info("browser_stopped")

    async def get_context(self, name: str = "default") -> BrowserContext:
        """Get or create a named browser context.

        Each adapter should use its shop_slug as the context name
        so contexts are reused within the same shop but isolated
        between different shops.
        """
        if name in self._contexts:
            return self._contexts[name]

        if not self._browser:
            await self.start()

        proxy_url = self._proxy_manager.get_proxy()
        proxy_config = None
        if proxy_url:
            proxy_config = {"server": proxy_url}

        context = await self._browser.new_context(
            user_agent=get_random_user_agent(),
            viewport={"width": 1920, "height": 1080},
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            proxy=proxy_config,
            java_script_enabled=True,
            bypass_csp=True,
        )

        # Inject stealth script to avoid detection
        await context.add_init_script(STEALTH_JS)

        # Block heavy resources for speed
        if self._block_resources:
            await context.route(
                "**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf,eot}",
                lambda route: route.abort(),
            )

        self._contexts[name] = context
        logger.info("browser_context_created", name=name, has_proxy=bool(proxy_url))
        return context

    async def new_page(self, name: str = "default"):
        """Convenience: get context and open a new page."""
        ctx = await self.get_context(name)
        return await ctx.new_page()

    async def close_context(self, name: str) -> None:
        """Close a specific context by name."""
        ctx = self._contexts.pop(name, None)
        if ctx:
            await ctx.close()


# Minimal stealth JS to mask automation signals
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['ko-KR', 'ko', 'en-US', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
window.chrome = { runtime: {} };
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) =>
  parameters.name === 'notifications'
    ? Promise.resolve({ state: Notification.permission })
    : originalQuery(parameters);
"""


# Singleton instance
_browser_manager: Optional[BrowserManager] = None


def get_browser_manager() -> BrowserManager:
    """Get the global BrowserManager singleton."""
    global _browser_manager
    if _browser_manager is None:
        proxy_urls = settings.get_proxy_list()
        pm = ProxyManager(proxy_urls) if proxy_urls else NoProxyManager()
        _browser_manager = BrowserManager(proxy_manager=pm)
    return _browser_manager
