"""Custom exception classes for the application."""


class DealHawkException(Exception):
    """Base exception for all DealHawk errors."""

    def __init__(self, message: str = "An unexpected error occurred"):
        self.message = message
        super().__init__(self.message)


class NotFoundError(DealHawkException):
    """Raised when a requested resource is not found."""

    def __init__(self, resource: str, identifier: str):
        super().__init__(f"{resource} with identifier '{identifier}' not found")


class ScraperError(DealHawkException):
    """Raised when a scraper encounters an error."""

    def __init__(self, platform: str, message: str):
        super().__init__(f"Scraper error for {platform}: {message}")


class RateLimitError(DealHawkException):
    """Raised when an external API rate limit is hit."""

    def __init__(self, platform: str):
        super().__init__(f"Rate limit exceeded for {platform}")
