"""Shop-specific adapter implementations.

Each adapter module should implement a class that inherits from
BaseAdapter (for API adapters) or BaseScraperAdapter (for scraping adapters).
"""

# Import API adapters
from .naver import NaverShoppingAdapter
from .coupang import CoupangAdapter
from .eleven_st import ElevenStAdapter
from .aliexpress import AliExpressAdapter
from .amazon import AmazonAdapter
from .steam import SteamAdapter
from .ebay import EbayAdapter
from .newegg import NeweggAdapter

# Import scraper adapters
from .gmarket import GmarketAdapter
from .auction import AuctionAdapter
from .ssg import SSGAdapter
from .himart import HimartAdapter
from .lotteon import LotteonAdapter
from .interpark import InterparkAdapter
from .musinsa import MusinsaAdapter
from .ssf import SSFAdapter
from .taobao import TaobaoAdapter

__all__ = [
    # API adapters
    "NaverShoppingAdapter",
    "CoupangAdapter",
    "ElevenStAdapter",
    "AliExpressAdapter",
    "AmazonAdapter",
    "SteamAdapter",
    "EbayAdapter",
    "NeweggAdapter",
    # Scraper adapters
    "GmarketAdapter",
    "AuctionAdapter",
    "SSGAdapter",
    "HimartAdapter",
    "LotteonAdapter",
    "InterparkAdapter",
    "MusinsaAdapter",
    "SSFAdapter",
    "TaobaoAdapter",
]
