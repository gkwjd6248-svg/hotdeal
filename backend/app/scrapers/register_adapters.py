"""Register all scraper adapters with the factory.

This module should be imported during application startup to register
all available adapters with the adapter factory.
"""

import structlog

from app.scrapers.factory import get_adapter_factory
from app.scrapers.adapters import (
    # API adapters
    NaverShoppingAdapter,
    CoupangAdapter,
    ElevenStAdapter,
    SteamAdapter,
    AliExpressAdapter,
    AmazonAdapter,
    EbayAdapter,
    NeweggAdapter,
    # Scraper adapters
    GmarketAdapter,
    AuctionAdapter,
    SSGAdapter,
    HimartAdapter,
    LotteonAdapter,
    InterparkAdapter,
    MusinsaAdapter,
    SSFAdapter,
    TaobaoAdapter,
)

logger = structlog.get_logger(__name__)


def register_all_adapters() -> None:
    """Register all available adapters with the factory.

    This should be called during application startup.
    """
    factory = get_adapter_factory()

    # Register adapters
    adapters = [
        # Korean API shops (Phase 2)
        ("naver", NaverShoppingAdapter),
        ("coupang", CoupangAdapter),
        ("11st", ElevenStAdapter),
        # International API shops (Phase 3)
        ("steam", SteamAdapter),
        ("aliexpress", AliExpressAdapter),
        ("amazon", AmazonAdapter),
        ("ebay", EbayAdapter),
        ("newegg", NeweggAdapter),
        # Korean scraper shops (Phase 4)
        ("gmarket", GmarketAdapter),
        ("auction", AuctionAdapter),
        ("ssg", SSGAdapter),
        ("himart", HimartAdapter),
        ("lotteon", LotteonAdapter),
        ("interpark", InterparkAdapter),
        ("musinsa", MusinsaAdapter),
        ("ssf", SSFAdapter),
        # Chinese scraper shops (Phase 5)
        ("taobao", TaobaoAdapter),
    ]

    for shop_slug, adapter_class in adapters:
        try:
            factory.register_adapter(shop_slug, adapter_class)
            logger.info(
                "adapter_registered",
                shop_slug=shop_slug,
                adapter_class=adapter_class.__name__,
            )
        except Exception as e:
            logger.error(
                "adapter_registration_failed",
                shop_slug=shop_slug,
                error=str(e),
                exc_info=True,
            )

    logger.info(
        "all_adapters_registered",
        count=len(factory.get_registered_shops()),
        shops=factory.get_registered_shops(),
    )
