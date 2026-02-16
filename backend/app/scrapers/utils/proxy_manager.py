"""Rotating proxy pool with health checking."""

import random
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, timedelta


@dataclass
class ProxyEntry:
    """Proxy configuration entry with health tracking."""

    url: str  # Proxy URL (e.g., "http://user:pass@host:port" or "socks5://host:port")
    healthy: bool = True
    fail_count: int = 0
    success_count: int = 0
    last_used: Optional[datetime] = None
    last_failed: Optional[datetime] = None
    last_success: Optional[datetime] = None

    def mark_failed(self) -> None:
        """Mark this proxy as having failed a request."""
        self.fail_count += 1
        self.last_failed = datetime.utcnow()
        # Mark unhealthy after 3 consecutive failures
        if self.fail_count >= 3:
            self.healthy = False

    def mark_success(self) -> None:
        """Mark this proxy as having succeeded a request."""
        self.success_count += 1
        self.fail_count = 0  # Reset consecutive failures
        self.healthy = True
        self.last_success = datetime.utcnow()

    def should_retry(self, cooldown_minutes: int = 10) -> bool:
        """Check if an unhealthy proxy should be retried.

        Args:
            cooldown_minutes: Minutes to wait before retrying failed proxy

        Returns:
            True if proxy should be retried
        """
        if self.healthy:
            return True
        if not self.last_failed:
            return True
        cooldown = timedelta(minutes=cooldown_minutes)
        return datetime.utcnow() - self.last_failed > cooldown


class ProxyManager:
    """Rotating proxy pool with health checking and automatic failover.

    Manages a pool of proxies, rotating through healthy ones and
    automatically marking failed proxies as unhealthy. Failed proxies
    are periodically retried after a cooldown period.
    """

    def __init__(
        self,
        proxy_urls: List[str],
        strategy: str = "round-robin",
        cooldown_minutes: int = 10,
    ):
        """Initialize proxy manager.

        Args:
            proxy_urls: List of proxy URLs
            strategy: Selection strategy ('round-robin' or 'random')
            cooldown_minutes: Minutes to wait before retrying failed proxy
        """
        self.proxies = [ProxyEntry(url=url) for url in proxy_urls]
        self.strategy = strategy
        self.cooldown_minutes = cooldown_minutes
        self._index = 0

    def get_proxy(self) -> Optional[str]:
        """Get next proxy from the pool.

        Returns:
            Proxy URL string, or None if no proxies available

        Note:
            Automatically skips unhealthy proxies and retries failed
            proxies after cooldown period.
        """
        if not self.proxies:
            return None

        # Get healthy proxies or those ready for retry
        available = [
            p for p in self.proxies if p.healthy or p.should_retry(self.cooldown_minutes)
        ]

        if not available:
            # All proxies are unhealthy and on cooldown
            # Reset all proxies as last resort
            for p in self.proxies:
                p.healthy = True
                p.fail_count = 0
            available = self.proxies

        # Select proxy based on strategy
        if self.strategy == "random":
            proxy = random.choice(available)
        else:  # round-robin
            proxy = available[self._index % len(available)]
            self._index = (self._index + 1) % len(available)

        proxy.last_used = datetime.utcnow()
        return proxy.url

    def mark_failed(self, proxy_url: str) -> None:
        """Mark a proxy as failed.

        Args:
            proxy_url: The proxy URL that failed
        """
        for p in self.proxies:
            if p.url == proxy_url:
                p.mark_failed()
                break

    def mark_success(self, proxy_url: str) -> None:
        """Mark a proxy as successful.

        Args:
            proxy_url: The proxy URL that succeeded
        """
        for p in self.proxies:
            if p.url == proxy_url:
                p.mark_success()
                break

    def get_stats(self) -> dict:
        """Get statistics about proxy pool health.

        Returns:
            Dictionary with proxy pool statistics
        """
        total = len(self.proxies)
        healthy = sum(1 for p in self.proxies if p.healthy)
        unhealthy = total - healthy
        total_requests = sum(p.success_count + p.fail_count for p in self.proxies)
        success_rate = 0.0

        if total_requests > 0:
            total_success = sum(p.success_count for p in self.proxies)
            success_rate = (total_success / total_requests) * 100

        return {
            "total_proxies": total,
            "healthy_proxies": healthy,
            "unhealthy_proxies": unhealthy,
            "total_requests": total_requests,
            "success_rate_percent": round(success_rate, 2),
        }

    def reset_all(self) -> None:
        """Reset all proxies to healthy state.

        Useful for manual recovery or testing.
        """
        for p in self.proxies:
            p.healthy = True
            p.fail_count = 0

    def remove_proxy(self, proxy_url: str) -> bool:
        """Remove a proxy from the pool.

        Args:
            proxy_url: The proxy URL to remove

        Returns:
            True if proxy was removed, False if not found
        """
        for i, p in enumerate(self.proxies):
            if p.url == proxy_url:
                self.proxies.pop(i)
                return True
        return False

    def add_proxy(self, proxy_url: str) -> None:
        """Add a new proxy to the pool.

        Args:
            proxy_url: The proxy URL to add
        """
        # Check if proxy already exists
        if any(p.url == proxy_url for p in self.proxies):
            return
        self.proxies.append(ProxyEntry(url=proxy_url))


class NoProxyManager(ProxyManager):
    """Dummy proxy manager that returns None (no proxy).

    Useful for development or when proxies are not needed.
    """

    def __init__(self):
        """Initialize with empty proxy list."""
        super().__init__([])

    def get_proxy(self) -> Optional[str]:
        """Always return None (no proxy)."""
        return None
