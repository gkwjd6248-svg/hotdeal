"""Data normalization utilities for price parsing and category classification."""

import re
import time
from decimal import Decimal, InvalidOperation
from typing import Optional, Dict

import httpx
import structlog

logger = structlog.get_logger()


# Keyword-based category classifier for automatic categorization
CATEGORY_KEYWORDS = {
    "pc-hardware": [
        # GPUs (avoid short "RX" - too many false positives in Korean text)
        "그래픽카드", "GPU", "RTX ", "GTX ", "Radeon",
        # CPUs (use space-suffixed to avoid false matches like "birx", "미i3")
        "CPU", "프로세서", "라이젠", "Ryzen", "인텔 ", "Intel ",
        # Storage
        "SSD", "NVMe", "HDD", "M.2",
        # Memory
        "RAM", "DDR5", "DDR4",
        # Motherboards
        "메인보드", "마더보드",
        # PSU
        "파워서플라이",
        # Cooling
        "수냉쿨러", "공랭쿨러",
    ],
    "laptop-mobile": [
        # Laptops
        "노트북", "laptop", "맥북", "MacBook", "갤럭시북", "LG그램",
        # Smartphones
        "스마트폰", "갤럭시 S", "갤럭시 Z", "Galaxy S", "Galaxy Z",
        "iPhone", "아이폰",
        # Tablets
        "태블릿", "iPad", "아이패드", "갤럭시탭",
    ],
    "electronics-tv": [
        # TVs & Monitors
        "TV", "텔레비전", "모니터", "디스플레이", "OLED", "QLED",
        # Home Appliances
        "세탁기", "냉장고", "에어컨", "건조기", "청소기", "공기청정기", "로봇청소기",
        "전자레인지", "식기세척기", "정수기", "에어프라이어",
        # Audio
        "이어폰", "헤드폰", "스피커", "사운드바",
    ],
    "games-software": [
        # Games
        "게임", "game", "Steam", "스팀",
        # Consoles
        "PS5", "플레이스테이션", "PlayStation", "Xbox", "엑스박스",
        "닌텐도", "Nintendo",
        # Software
        "소프트웨어", "라이선스", "윈도우", "Windows", "오피스", "Office",
    ],
    "gift-cards": [
        "상품권", "기프트카드", "gift card", "쿠폰", "포인트",
        "문화상품권", "해피머니", "북앤라이프", "스타벅스",
    ],
    "fashion-beauty": [
        # Fashion
        "원피스", "드레스", "블라우스", "티셔츠", "셔츠", "자켓", "코트",
        "패딩", "점퍼", "바지", "청바지", "스커트", "니트", "가디건",
        "운동화", "스니커즈", "구두", "샌들", "슬리퍼", "부츠",
        "가방", "백팩", "핸드백", "지갑", "벨트", "모자",
        # Beauty
        "화장품", "스킨케어", "로션", "세럼", "선크림", "마스크팩",
        "립스틱", "파운데이션", "향수",
        # Brands
        "나이키", "아디다스", "뉴발란스", "Nike", "Adidas",
    ],
    "living-food": [
        # Food & Beverage
        "식품", "생수", "과자", "커피", "라면", "음료", "간식", "건강식품", "영양제",
        "선물세트", "과일", "정육", "수산", "반찬", "견과", "초콜릿",
        # Living & Household
        "세제", "화장지", "샴푸", "비누", "주방", "욕실", "세탁",
        "수건", "침구", "이불", "베개", "매트리스",
    ],
}


class CurrencyConverter:
    """Manages exchange rates with periodic live updates.

    Fetches live rates from exchangerate.host (free, no key required)
    and falls back to hardcoded rates if the API is unavailable.
    Rates are cached in memory with a configurable TTL.
    """

    # Fallback exchange rates to KRW
    _FALLBACK_RATES: Dict[str, Decimal] = {
        "USD": Decimal("1350"),
        "CNY": Decimal("185"),
        "JPY": Decimal("9"),
        "EUR": Decimal("1450"),
        "GBP": Decimal("1650"),
        "KRW": Decimal("1"),
    }

    _live_rates: Dict[str, Decimal] = {}
    _last_fetched: float = 0
    _ttl_seconds: int = 3600  # 1 hour

    @classmethod
    async def refresh_rates(cls) -> bool:
        """Fetch live exchange rates from API.

        Returns:
            True if rates were successfully updated
        """
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.exchangerate-api.com/v4/latest/KRW"
                )
                resp.raise_for_status()
                data = resp.json()

            rates_from_krw = data.get("rates", {})
            new_rates: Dict[str, Decimal] = {"KRW": Decimal("1")}
            for code in ("USD", "CNY", "JPY", "EUR", "GBP"):
                rate_from_krw = rates_from_krw.get(code)
                if rate_from_krw and float(rate_from_krw) > 0:
                    # API gives KRW→X, we need X→KRW (inverse)
                    new_rates[code] = (Decimal("1") / Decimal(str(rate_from_krw))).quantize(Decimal("0.01"))

            cls._live_rates = new_rates
            cls._last_fetched = time.time()
            logger.info("exchange_rates_updated", rates={k: str(v) for k, v in new_rates.items()})
            return True
        except Exception as e:
            logger.warning("exchange_rate_fetch_failed", error=str(e))
            return False

    @classmethod
    def get_rate(cls, currency: str) -> Decimal:
        """Get exchange rate to KRW for given currency.

        Uses live rates if available and fresh, otherwise falls back
        to hardcoded rates.
        """
        currency = currency.upper()
        if cls._live_rates and (time.time() - cls._last_fetched < cls._ttl_seconds):
            return cls._live_rates.get(currency, cls._FALLBACK_RATES.get(currency, Decimal("1")))
        return cls._FALLBACK_RATES.get(currency, Decimal("1"))

    @classmethod
    def to_krw(cls, price: Decimal, currency: str) -> Decimal:
        """Convert price to KRW."""
        rate = cls.get_rate(currency)
        return (price * rate).quantize(Decimal("1"))


class PriceNormalizer:
    """Price parsing and currency conversion utilities.

    Handles parsing price strings from various formats and
    converting foreign currencies to KRW for consistent storage.
    """

    # Exchange rates to KRW (approximate, should be updated periodically)
    EXCHANGE_RATES = {
        "USD": Decimal("1350"),
        "CNY": Decimal("185"),
        "JPY": Decimal("9"),
        "EUR": Decimal("1450"),
        "GBP": Decimal("1650"),
        "KRW": Decimal("1"),
    }

    @classmethod
    def to_krw(cls, price: Decimal, currency: str) -> Decimal:
        """Convert price to KRW using exchange rates.

        Uses CurrencyConverter for live rates when available,
        falls back to static rates.

        Args:
            price: Price amount
            currency: Currency code (USD, EUR, CNY, etc.)

        Returns:
            Price converted to KRW, rounded to whole number
        """
        return CurrencyConverter.to_krw(price, currency)

    @staticmethod
    def clean_price_string(raw: str) -> Optional[Decimal]:
        """Parse a price string and extract numeric value.

        Handles various formats:
        - "1,234원" -> 1234
        - "$12.99" -> 12.99
        - "¥1,234" -> 1234
        - "1234.56" -> 1234.56

        Args:
            raw: Raw price string

        Returns:
            Decimal price value, or None if parsing fails
        """
        if not raw:
            return None

        # Remove common currency symbols and whitespace
        cleaned = raw.replace("원", "").replace("₩", "").replace("$", "")
        cleaned = cleaned.replace("¥", "").replace("€", "").replace("£", "")
        cleaned = cleaned.strip()

        # Remove thousand separators (commas)
        cleaned = cleaned.replace(",", "")

        # Remove any remaining non-digit/non-decimal characters
        cleaned = re.sub(r"[^\d.]", "", cleaned)

        if not cleaned:
            return None

        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return None

    @staticmethod
    def extract_price_from_text(text: str) -> Optional[Decimal]:
        """Extract first price-like number from text.

        Useful for extracting prices from HTML text nodes that
        contain additional text.

        Args:
            text: Text containing price information

        Returns:
            Extracted price as Decimal, or None if not found
        """
        if not text:
            return None

        # Look for patterns like "12,345" or "12345" or "12,345.67"
        pattern = r"[\d,]+\.?\d*"
        matches = re.findall(pattern, text)

        for match in matches:
            price = PriceNormalizer.clean_price_string(match)
            if price and price > 0:
                return price

        return None


class CategoryClassifier:
    """Automatic category classification based on product title keywords.

    Uses keyword matching to suggest a category for products.
    This is used as a hint for manual categorization or as a fallback.
    """

    @staticmethod
    def classify(title: str, shop_category: Optional[str] = None) -> Optional[str]:
        """Classify product into a category based on title.

        Args:
            title: Product title
            shop_category: Optional category hint from shop

        Returns:
            Category slug (e.g., "pc-hardware") or None
        """
        if not title:
            return None

        title_lower = title.lower()
        scores = {}

        # Score each category based on keyword matches
        for cat_slug, keywords in CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in title_lower)
            if score > 0:
                scores[cat_slug] = score

        # Return category with highest score
        if scores:
            return max(scores, key=scores.get)

        return None

    @staticmethod
    def classify_with_confidence(
        title: str, shop_category: Optional[str] = None
    ) -> tuple[Optional[str], float]:
        """Classify product with confidence score.

        Args:
            title: Product title
            shop_category: Optional category hint from shop

        Returns:
            Tuple of (category_slug, confidence_score)
            Confidence is 0.0 to 1.0
        """
        if not title:
            return None, 0.0

        title_lower = title.lower()
        scores = {}
        total_keywords = 0

        # Score each category based on keyword matches
        for cat_slug, keywords in CATEGORY_KEYWORDS.items():
            total_keywords += len(keywords)
            score = sum(1 for kw in keywords if kw.lower() in title_lower)
            if score > 0:
                scores[cat_slug] = score

        if not scores:
            return None, 0.0

        best_category = max(scores, key=scores.get)
        best_score = scores[best_category]

        # Confidence is based on number of matching keywords
        # and relative score compared to other categories
        max_possible = len(CATEGORY_KEYWORDS[best_category])
        confidence = min(1.0, best_score / max(3, max_possible) * 2)

        return best_category, confidence


def normalize_url(url: str) -> str:
    """Normalize a URL by removing tracking parameters.

    Args:
        url: URL to normalize

    Returns:
        Normalized URL
    """
    if not url:
        return url

    # Common tracking parameters to remove
    tracking_params = [
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_content",
        "utm_term",
        "ref",
        "source",
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
    ]

    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)

    # Remove tracking parameters
    filtered_params = {
        k: v for k, v in query_params.items() if k not in tracking_params
    }

    # Rebuild query string
    new_query = urlencode(filtered_params, doseq=True)

    # Rebuild URL
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, "")
    )
