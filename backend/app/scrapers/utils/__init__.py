"""Scraper utilities for rate limiting, proxy management, and data normalization."""

from .rate_limiter import DomainRateLimiter, TokenBucket
from .proxy_manager import ProxyManager, ProxyEntry, NoProxyManager
from .user_agents import (
    get_random_user_agent,
    get_chrome_user_agent,
    get_firefox_user_agent,
    get_safari_user_agent,
    get_mobile_user_agent,
    get_user_agent_by_browser,
    USER_AGENTS,
)
from .normalizer import (
    PriceNormalizer,
    CategoryClassifier,
    normalize_url,
    CATEGORY_KEYWORDS,
)
from .retry import http_retry, playwright_retry, critical_retry


__all__ = [
    # Rate limiting
    "DomainRateLimiter",
    "TokenBucket",
    # Proxy management
    "ProxyManager",
    "ProxyEntry",
    "NoProxyManager",
    # User agents
    "get_random_user_agent",
    "get_chrome_user_agent",
    "get_firefox_user_agent",
    "get_safari_user_agent",
    "get_mobile_user_agent",
    "get_user_agent_by_browser",
    "USER_AGENTS",
    # Normalization
    "PriceNormalizer",
    "CategoryClassifier",
    "normalize_url",
    "CATEGORY_KEYWORDS",
    # Retry decorators
    "http_retry",
    "playwright_retry",
    "critical_retry",
]
