"""Token bucket rate limiter for per-domain rate limiting."""

import asyncio
import time
from typing import Dict


class TokenBucket:
    """Token bucket algorithm implementation for rate limiting.

    The bucket starts full and refills at a constant rate.
    Each request consumes one token. If no tokens are available,
    the request waits until tokens are refilled.
    """

    def __init__(self, rate: float, capacity: float):
        """Initialize token bucket.

        Args:
            rate: Tokens per second (e.g., 1.0 = 60 RPM)
            capacity: Maximum tokens in bucket (burst capacity)
        """
        self.rate = rate  # tokens per second
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time since last refill."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now

    async def acquire(self, tokens: float = 1.0) -> None:
        """Acquire tokens from the bucket, waiting if necessary.

        Args:
            tokens: Number of tokens to acquire (default 1.0)
        """
        async with self._lock:
            while True:
                self._refill()
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return
                # Calculate wait time until we have enough tokens
                wait_time = (tokens - self.tokens) / self.rate
                await asyncio.sleep(wait_time)


class DomainRateLimiter:
    """Per-domain rate limiter using token bucket algorithm.

    Each domain gets its own token bucket with a configured rate limit.
    This prevents overwhelming any single target server while allowing
    concurrent scraping of multiple domains.
    """

    # Rate limits in requests per minute (RPM) for known domains
    DOMAIN_LIMITS_RPM = {
        # Korean e-commerce
        "www.coupang.com": 60,
        "shopping.naver.com": 60,
        "openapi.11st.co.kr": 30,
        "www.11st.co.kr": 30,
        "www.e-himart.co.kr": 10,
        "www.ssg.com": 10,
        "www.lotteon.com": 10,
        "www.musinsa.com": 10,
        "www.auction.co.kr": 15,
        "www.gmarket.co.kr": 15,
        "www.interpark.com": 10,
        "www.ssfshop.com": 10,
        # International e-commerce APIs
        "api.ebay.com": 60,
        "webservices.amazon.com": 60,  # 1 req/sec for PA-API
        "openservice.aliexpress.com": 3,
        "api-sg.aliexpress.com": 3,
        # Other domains
        "store.steampowered.com": 10,
        "www.newegg.com": 15,
        "s.taobao.com": 5,
        "world.taobao.com": 5,
    }

    # Default rate limit for unknown domains
    DEFAULT_RPM = 10

    def __init__(self):
        """Initialize rate limiter with empty bucket dictionary."""
        self._buckets: Dict[str, TokenBucket] = {}

    def _get_bucket(self, domain: str) -> TokenBucket:
        """Get or create token bucket for a domain.

        Args:
            domain: Domain name (e.g., "www.coupang.com")

        Returns:
            TokenBucket instance for this domain
        """
        if domain not in self._buckets:
            rpm = self.DOMAIN_LIMITS_RPM.get(domain, self.DEFAULT_RPM)
            rate = rpm / 60.0  # convert RPM to requests per second
            # Capacity allows small bursts (10% of RPM, min 2)
            capacity = max(2.0, rpm / 10.0)
            self._buckets[domain] = TokenBucket(rate=rate, capacity=capacity)
        return self._buckets[domain]

    async def acquire(self, domain: str, tokens: float = 1.0) -> None:
        """Acquire rate limit token for a domain.

        This method will block until rate limit allows the request.

        Args:
            domain: Domain name to rate limit
            tokens: Number of tokens to acquire (default 1.0)
        """
        bucket = self._get_bucket(domain)
        await bucket.acquire(tokens)

    def set_custom_limit(self, domain: str, rpm: int) -> None:
        """Set a custom rate limit for a domain.

        Args:
            domain: Domain name
            rpm: Requests per minute limit

        Note:
            If a bucket already exists for this domain, it will be replaced.
        """
        rate = rpm / 60.0
        capacity = max(2.0, rpm / 10.0)
        self._buckets[domain] = TokenBucket(rate=rate, capacity=capacity)

    def get_current_rate(self, domain: str) -> float:
        """Get the current rate limit (RPM) for a domain.

        Args:
            domain: Domain name

        Returns:
            Current rate limit in requests per minute
        """
        bucket = self._get_bucket(domain)
        return bucket.rate * 60.0
