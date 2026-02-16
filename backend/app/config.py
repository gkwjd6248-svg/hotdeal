"""Application configuration via Pydantic Settings."""

from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://dealhawk:dealhawk_dev@localhost:5432/dealhawk"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # App
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Naver API
    NAVER_CLIENT_ID: str = ""
    NAVER_CLIENT_SECRET: str = ""

    # Coupang Partners API
    COUPANG_ACCESS_KEY: str = ""
    COUPANG_SECRET_KEY: str = ""

    # 11st API
    ELEVEN_ST_API_KEY: str = ""

    # AliExpress API
    ALIEXPRESS_APP_KEY: str = ""
    ALIEXPRESS_APP_SECRET: str = ""

    # Amazon PA-API
    AMAZON_ACCESS_KEY: str = ""
    AMAZON_SECRET_KEY: str = ""
    AMAZON_PARTNER_TAG: str = ""

    # eBay API
    EBAY_CLIENT_ID: str = ""
    EBAY_CLIENT_SECRET: str = ""

    # Proxy
    PROXY_LIST: str = ""  # Comma-separated list of proxy URLs

    # Auth / JWT
    JWT_SECRET_KEY: str = "change-me-in-production-use-a-random-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Frontend
    FRONTEND_URL: str = "http://localhost:3000"
    REVALIDATION_SECRET: str = "your-secret-here"

    def get_proxy_list(self) -> List[str]:
        """Parse PROXY_LIST into a list of proxy URLs.

        Returns:
            List of proxy URL strings, empty if PROXY_LIST is not set
        """
        if not self.PROXY_LIST:
            return []
        return [p.strip() for p in self.PROXY_LIST.split(",") if p.strip()]


settings = Settings()
