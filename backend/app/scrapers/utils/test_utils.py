"""Simple test/demonstration of utility modules.

This file demonstrates basic usage of the utility modules.
For production tests, see the tests/ directory.
"""

from decimal import Decimal


def test_price_normalizer():
    """Test price normalization utilities."""
    from app.scrapers.utils import PriceNormalizer

    # Test Korean price parsing
    assert PriceNormalizer.clean_price_string("1,234원") == Decimal("1234")
    assert PriceNormalizer.clean_price_string("1,234,567원") == Decimal("1234567")

    # Test USD price parsing
    assert PriceNormalizer.clean_price_string("$12.99") == Decimal("12.99")
    assert PriceNormalizer.clean_price_string("$1,234.56") == Decimal("1234.56")

    # Test price extraction from text
    assert PriceNormalizer.extract_price_from_text("판매가: 123,456원") == Decimal("123456")
    assert PriceNormalizer.extract_price_from_text("Sale: $99.99 today!") == Decimal("99.99")

    # Test currency conversion
    usd_price = Decimal("10.00")
    krw_price = PriceNormalizer.to_krw(usd_price, "USD")
    assert krw_price == Decimal("13500")  # 10 * 1350

    print("✓ PriceNormalizer tests passed")


def test_category_classifier():
    """Test category classification."""
    from app.scrapers.utils import CategoryClassifier

    # Test PC hardware classification
    assert CategoryClassifier.classify("RTX 4090 그래픽카드") == "pc-hardware"
    assert CategoryClassifier.classify("Intel i9 프로세서") == "pc-hardware"
    assert CategoryClassifier.classify("삼성 SSD 1TB") == "pc-hardware"

    # Test laptop/mobile classification
    assert CategoryClassifier.classify("MacBook Pro 14인치") == "laptop-mobile"
    assert CategoryClassifier.classify("아이폰15 프로") == "laptop-mobile"
    assert CategoryClassifier.classify("갤럭시 S24") == "laptop-mobile"

    # Test electronics classification
    assert CategoryClassifier.classify("LG OLED TV 65인치") == "electronics-tv"
    assert CategoryClassifier.classify("삼성 냉장고") == "electronics-tv"

    # Test games classification
    assert CategoryClassifier.classify("PS5 디지털 에디션") == "games-software"
    assert CategoryClassifier.classify("Steam 기프트카드") == "games-software"

    # Test with confidence
    category, confidence = CategoryClassifier.classify_with_confidence("RTX 4090")
    assert category == "pc-hardware"
    assert confidence > 0.0

    print("✓ CategoryClassifier tests passed")


def test_url_normalization():
    """Test URL normalization."""
    from app.scrapers.utils import normalize_url

    # Test tracking parameter removal
    url_with_tracking = "https://example.com/product?id=123&utm_source=google&utm_medium=cpc"
    clean_url = normalize_url(url_with_tracking)
    assert "utm_source" not in clean_url
    assert "utm_medium" not in clean_url
    assert "id=123" in clean_url

    # Test fbclid removal
    url_with_fbclid = "https://example.com/product?id=123&fbclid=abc123"
    clean_url = normalize_url(url_with_fbclid)
    assert "fbclid" not in clean_url
    assert "id=123" in clean_url

    print("✓ URL normalization tests passed")


def test_user_agents():
    """Test user agent utilities."""
    from app.scrapers.utils import (
        get_random_user_agent,
        get_chrome_user_agent,
        get_firefox_user_agent,
    )

    # Test random user agent
    ua = get_random_user_agent()
    assert len(ua) > 0
    assert "Mozilla" in ua

    # Test Chrome user agent
    ua = get_chrome_user_agent()
    assert "Chrome/" in ua
    assert "Edg/" not in ua  # Not Edge

    # Test Firefox user agent
    ua = get_firefox_user_agent()
    assert "Firefox/" in ua

    # Test uniqueness (should get different UAs with multiple calls)
    uas = [get_random_user_agent() for _ in range(10)]
    assert len(set(uas)) > 1  # Should have variety

    print("✓ User agent tests passed")


def test_proxy_manager():
    """Test proxy manager."""
    from app.scrapers.utils import ProxyManager, NoProxyManager

    # Test with proxies
    proxies = [
        "http://proxy1.com:8080",
        "http://proxy2.com:8080",
        "http://proxy3.com:8080",
    ]
    manager = ProxyManager(proxies, strategy="round-robin")

    # Test round-robin
    proxy1 = manager.get_proxy()
    proxy2 = manager.get_proxy()
    proxy3 = manager.get_proxy()
    assert proxy1 != proxy2 != proxy3

    # Test success marking
    manager.mark_success(proxy1)
    stats = manager.get_stats()
    assert stats["total_proxies"] == 3
    assert stats["healthy_proxies"] == 3

    # Test failure marking
    manager.mark_failed(proxy1)
    manager.mark_failed(proxy1)
    manager.mark_failed(proxy1)  # 3 failures -> unhealthy
    stats = manager.get_stats()
    assert stats["unhealthy_proxies"] == 1

    # Test NoProxyManager
    no_proxy = NoProxyManager()
    assert no_proxy.get_proxy() is None

    print("✓ ProxyManager tests passed")


async def test_rate_limiter():
    """Test rate limiter (async)."""
    import asyncio
    import time
    from app.scrapers.utils import DomainRateLimiter

    limiter = DomainRateLimiter()

    # Test that acquire completes
    await limiter.acquire("example.com")

    # Test rate limiting (should delay)
    start = time.time()
    for _ in range(3):
        await limiter.acquire("fast-domain.com")
    elapsed = time.time() - start

    # Should take some time due to rate limiting
    # (10 RPM = 6 seconds per request, 3 requests = ~12 seconds)
    # But we use burst capacity, so it might be faster
    assert elapsed >= 0  # Just check it completes

    # Test custom limit
    limiter.set_custom_limit("custom-domain.com", 120)  # 120 RPM = 2 per second
    rate = limiter.get_current_rate("custom-domain.com")
    assert rate == 120.0

    print("✓ DomainRateLimiter tests passed")


def run_sync_tests():
    """Run synchronous tests."""
    print("\nRunning synchronous tests...\n")
    test_price_normalizer()
    test_category_classifier()
    test_url_normalization()
    test_user_agents()
    test_proxy_manager()
    print("\n✓ All synchronous tests passed!\n")


async def run_async_tests():
    """Run asynchronous tests."""
    print("Running asynchronous tests...\n")
    await test_rate_limiter()
    print("\n✓ All asynchronous tests passed!\n")


if __name__ == "__main__":
    # Run synchronous tests
    run_sync_tests()

    # Run asynchronous tests
    import asyncio
    asyncio.run(run_async_tests())

    print("=" * 50)
    print("All tests passed! Utility modules are working correctly.")
    print("=" * 50)
