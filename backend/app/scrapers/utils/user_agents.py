"""User-Agent rotation utilities for anti-detection."""

import random
from typing import List


# Realistic user-agent strings updated for 2025/2026
# Mix of Chrome, Firefox, Safari, and Edge on Windows and macOS
USER_AGENTS: List[str] = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    # Firefox on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    # Additional Chrome variants
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    # Chrome on Linux (less common but realistic)
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]


def get_random_user_agent() -> str:
    """Get a random user-agent string from the pool.

    Returns:
        Random user-agent string
    """
    return random.choice(USER_AGENTS)


def get_chrome_user_agent() -> str:
    """Get a random Chrome user-agent string.

    Returns:
        Random Chrome user-agent string
    """
    chrome_agents = [ua for ua in USER_AGENTS if "Chrome/" in ua and "Edg/" not in ua]
    return random.choice(chrome_agents)


def get_firefox_user_agent() -> str:
    """Get a random Firefox user-agent string.

    Returns:
        Random Firefox user-agent string
    """
    firefox_agents = [ua for ua in USER_AGENTS if "Firefox/" in ua]
    return random.choice(firefox_agents)


def get_safari_user_agent() -> str:
    """Get a random Safari user-agent string.

    Returns:
        Random Safari user-agent string
    """
    safari_agents = [ua for ua in USER_AGENTS if "Safari/" in ua and "Chrome/" not in ua]
    return random.choice(safari_agents)


def get_mobile_user_agent() -> str:
    """Get a mobile user-agent string.

    Returns:
        Mobile user-agent string (iOS Safari or Android Chrome)
    """
    mobile_agents = [
        # iPhone Safari
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
        # iPad Safari
        "Mozilla/5.0 (iPad; CPU OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
        # Android Chrome
        "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
    ]
    return random.choice(mobile_agents)


def get_user_agent_by_browser(browser_name: str) -> str:
    """Get user-agent string for specific browser.

    Args:
        browser_name: Browser name ('chrome', 'firefox', 'safari', 'edge', 'mobile')

    Returns:
        User-agent string for specified browser, or random if not recognized
    """
    browser_name = browser_name.lower()
    if browser_name == "chrome":
        return get_chrome_user_agent()
    elif browser_name == "firefox":
        return get_firefox_user_agent()
    elif browser_name == "safari":
        return get_safari_user_agent()
    elif browser_name == "mobile":
        return get_mobile_user_agent()
    else:
        return get_random_user_agent()
