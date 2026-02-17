"""Retry utilities with exponential backoff for HTTP requests."""

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import httpx
import structlog
try:
    from playwright.async_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError
except ImportError:
    PlaywrightError = Exception
    PlaywrightTimeoutError = TimeoutError


logger = structlog.get_logger(__name__)


# Reusable retry decorator for HTTP requests (httpx)
http_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(
        (
            httpx.HTTPStatusError,
            httpx.ConnectError,
            httpx.TimeoutException,
            httpx.ReadTimeout,
            httpx.ConnectTimeout,
        )
    ),
    before_sleep=before_sleep_log(logger, "warning"),
    reraise=True,
)


# Reusable retry decorator for Playwright scraping
playwright_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((PlaywrightError, PlaywrightTimeoutError)),
    before_sleep=before_sleep_log(logger, "warning"),
    reraise=True,
)


# More aggressive retry for critical operations
critical_retry = retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    retry=retry_if_exception_type(
        (
            httpx.HTTPStatusError,
            httpx.ConnectError,
            httpx.TimeoutException,
            PlaywrightError,
            PlaywrightTimeoutError,
        )
    ),
    before_sleep=before_sleep_log(logger, "warning"),
    reraise=True,
)
