"""Lightweight mock API server for local development without PostgreSQL/Redis.

Run with: uvicorn mock_server:app --reload --port 8000
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Query, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI(title="DealHawk Mock API", version="0.1.0-mock")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Mock Auth ---
# Simple token-based auth for mock (no real JWT)
MOCK_USERS = {}  # token -> user dict
MOCK_USERS_BY_EMAIL = {}  # email -> user dict


def _mock_token(user_id: str) -> str:
    return hashlib.sha256(user_id.encode()).hexdigest()[:32]


def _get_mock_user(authorization: Optional[str] = None):
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:]
    return MOCK_USERS.get(token)


class RegisterBody(BaseModel):
    email: str
    username: str
    password: str


class LoginBody(BaseModel):
    email: str
    password: str


class CommentBody(BaseModel):
    content: str
    parent_id: Optional[str] = None


class VoteBody(BaseModel):
    vote_type: str

# --- Mock Data ---

SHOPS = [
    {"id": str(uuid.uuid4()), "name": "쿠팡", "slug": "coupang", "logo_url": None, "country": "KR", "is_active": True, "deal_count": 3},
    {"id": str(uuid.uuid4()), "name": "네이버쇼핑", "slug": "naver", "logo_url": None, "country": "KR", "is_active": True, "deal_count": 2},
    {"id": str(uuid.uuid4()), "name": "11번가", "slug": "11st", "logo_url": None, "country": "KR", "is_active": True, "deal_count": 2},
    {"id": str(uuid.uuid4()), "name": "G마켓", "slug": "gmarket", "logo_url": None, "country": "KR", "is_active": True, "deal_count": 1},
    {"id": str(uuid.uuid4()), "name": "SSG.COM", "slug": "ssg", "logo_url": None, "country": "KR", "is_active": True, "deal_count": 2},
    {"id": str(uuid.uuid4()), "name": "롯데온", "slug": "lotteon", "logo_url": None, "country": "KR", "is_active": True, "deal_count": 1},
    {"id": str(uuid.uuid4()), "name": "알리익스프레스", "slug": "aliexpress", "logo_url": None, "country": "CN", "is_active": True, "deal_count": 1},
    {"id": str(uuid.uuid4()), "name": "옥션", "slug": "auction", "logo_url": None, "country": "KR", "is_active": True, "deal_count": 1},
    {"id": str(uuid.uuid4()), "name": "인터파크", "slug": "interpark", "logo_url": None, "country": "KR", "is_active": True, "deal_count": 1},
    {"id": str(uuid.uuid4()), "name": "무신사", "slug": "musinsa", "logo_url": None, "country": "KR", "is_active": True, "deal_count": 1},
    {"id": str(uuid.uuid4()), "name": "하이마트", "slug": "himart", "logo_url": None, "country": "KR", "is_active": True, "deal_count": 1},
    {"id": str(uuid.uuid4()), "name": "아마존", "slug": "amazon", "logo_url": None, "country": "US", "is_active": True, "deal_count": 2},
    {"id": str(uuid.uuid4()), "name": "이베이", "slug": "ebay", "logo_url": None, "country": "US", "is_active": True, "deal_count": 1},
    {"id": str(uuid.uuid4()), "name": "스팀", "slug": "steam", "logo_url": None, "country": "US", "is_active": True, "deal_count": 2},
    {"id": str(uuid.uuid4()), "name": "뉴에그", "slug": "newegg", "logo_url": None, "country": "US", "is_active": True, "deal_count": 1},
    {"id": str(uuid.uuid4()), "name": "SSF샵", "slug": "ssf", "logo_url": None, "country": "KR", "is_active": True, "deal_count": 1},
    {"id": str(uuid.uuid4()), "name": "타오바오", "slug": "taobao", "logo_url": None, "country": "CN", "is_active": True, "deal_count": 0},
]

CATEGORIES = [
    {"id": str(uuid.uuid4()), "name": "PC/하드웨어", "slug": "pc-hardware", "icon": "Cpu", "sort_order": 1, "deal_count": 2},
    {"id": str(uuid.uuid4()), "name": "상품권/쿠폰", "slug": "gift-cards", "icon": "Gift", "sort_order": 2, "deal_count": 1},
    {"id": str(uuid.uuid4()), "name": "게임/SW", "slug": "games-software", "icon": "Gamepad2", "sort_order": 3, "deal_count": 1},
    {"id": str(uuid.uuid4()), "name": "노트북/모바일", "slug": "laptop-mobile", "icon": "Smartphone", "sort_order": 4, "deal_count": 3},
    {"id": str(uuid.uuid4()), "name": "가전/TV", "slug": "electronics-tv", "icon": "Tv", "sort_order": 5, "deal_count": 4},
    {"id": str(uuid.uuid4()), "name": "생활/식품", "slug": "living-food", "icon": "ShoppingBasket", "sort_order": 6, "deal_count": 1},
]

now = datetime.now(timezone.utc)

def _shop(slug: str):
    return next((s for s in SHOPS if s["slug"] == slug), SHOPS[0])

def _cat(slug: str):
    return next((c for c in CATEGORIES if c["slug"] == slug), CATEGORIES[0])

DEALS = [
    {
        "id": str(uuid.uuid4()),
        "title": "삼성 갤럭시 버즈2 프로 노이즈캔슬링 무선 이어폰",
        "deal_price": 149000, "original_price": 229000, "discount_percentage": 35,
        "ai_score": 92, "ai_reasoning": "높은 할인율과 우수한 제품 평가",
        "deal_type": "flash_sale", "deal_url": "https://www.coupang.com/vp/products/123456",
        "image_url": "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=400&h=300&fit=crop",
        "is_active": True, "expires_at": None,
        "created_at": (now - timedelta(hours=2)).isoformat(),
        "view_count": 1243, "vote_up": 89, "comment_count": 23,
        "shop": {"name": "쿠팡", "slug": "coupang", "logo_url": None, "country": "KR"},
        "category": {"name": "노트북/모바일", "slug": "laptop-mobile"},
    },
    {
        "id": str(uuid.uuid4()),
        "title": "LG 그램 17인치 노트북 2024년형 17Z90S (i7/16GB/512GB)",
        "deal_price": 1689000, "original_price": 2190000, "discount_percentage": 23,
        "ai_score": 88, "ai_reasoning": "프리미엄 제품 대폭 할인",
        "deal_type": "price_drop", "deal_url": "https://shopping.naver.com/product/123456",
        "image_url": "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=400&h=300&fit=crop",
        "is_active": True, "expires_at": None,
        "created_at": (now - timedelta(hours=4)).isoformat(),
        "view_count": 2341, "vote_up": 156, "comment_count": 45,
        "shop": {"name": "네이버쇼핑", "slug": "naver", "logo_url": None, "country": "KR"},
        "category": {"name": "노트북/모바일", "slug": "laptop-mobile"},
    },
    {
        "id": str(uuid.uuid4()),
        "title": "다이슨 V15 무선청소기 디텍트 압솔루트 (AS 2년 / 로켓배송)",
        "deal_price": 649000, "original_price": 1090000, "discount_percentage": 40,
        "ai_score": 95, "ai_reasoning": "베스트셀러 초특가",
        "deal_type": "clearance", "deal_url": "https://www.11st.co.kr/products/123456",
        "image_url": "https://images.unsplash.com/photo-1558317374-067fb5f30001?w=400&h=300&fit=crop",
        "is_active": True, "expires_at": (now + timedelta(hours=24)).isoformat(),
        "created_at": (now - timedelta(hours=1)).isoformat(),
        "view_count": 5234, "vote_up": 412, "comment_count": 89,
        "shop": {"name": "11번가", "slug": "11st", "logo_url": None, "country": "KR"},
        "category": {"name": "가전/TV", "slug": "electronics-tv"},
    },
    {
        "id": str(uuid.uuid4()),
        "title": "애플 에어팟 프로 2세대 MQD83KH/A 정품",
        "deal_price": 289000, "original_price": 359000, "discount_percentage": 19,
        "ai_score": 85, "ai_reasoning": "정품 최저가",
        "deal_type": "coupon", "deal_url": "https://www.gmarket.co.kr/item/123456",
        "image_url": "https://images.unsplash.com/photo-1606841837239-c5a1a4a07af7?w=400&h=300&fit=crop",
        "is_active": True, "expires_at": None,
        "created_at": (now - timedelta(hours=6)).isoformat(),
        "view_count": 3421, "vote_up": 234, "comment_count": 67,
        "shop": {"name": "G마켓", "slug": "gmarket", "logo_url": None, "country": "KR"},
        "category": {"name": "노트북/모바일", "slug": "laptop-mobile"},
    },
    {
        "id": str(uuid.uuid4()),
        "title": "로지텍 MX Master 3S 무선 마우스 블랙",
        "deal_price": 119000, "original_price": 149000, "discount_percentage": 20,
        "ai_score": 78, "ai_reasoning": "인기 제품 할인",
        "deal_type": "flash_sale", "deal_url": "https://www.ssg.com/item/123456",
        "image_url": "https://images.unsplash.com/photo-1527814050087-3793815479db?w=400&h=300&fit=crop",
        "is_active": True, "expires_at": None,
        "created_at": (now - timedelta(hours=8)).isoformat(),
        "view_count": 1876, "vote_up": 123, "comment_count": 34,
        "shop": {"name": "SSG.COM", "slug": "ssg", "logo_url": None, "country": "KR"},
        "category": {"name": "PC/하드웨어", "slug": "pc-hardware"},
    },
    {
        "id": str(uuid.uuid4()),
        "title": "필립스 에어프라이어 XXL 7.3L HD9650/91",
        "deal_price": 198000, "original_price": 359000, "discount_percentage": 45,
        "ai_score": 91, "ai_reasoning": "큰 할인폭, 우수 리뷰",
        "deal_type": "clearance", "deal_url": "https://www.lotteon.com/p/123456",
        "image_url": "https://images.unsplash.com/photo-1585515320310-259814833e62?w=400&h=300&fit=crop",
        "is_active": True, "expires_at": (now + timedelta(hours=48)).isoformat(),
        "created_at": (now - timedelta(hours=3)).isoformat(),
        "view_count": 2987, "vote_up": 276, "comment_count": 58,
        "shop": {"name": "롯데온", "slug": "lotteon", "logo_url": None, "country": "KR"},
        "category": {"name": "가전/TV", "slug": "electronics-tv"},
    },
    {
        "id": str(uuid.uuid4()),
        "title": "닌텐도 스위치 OLED 화이트 본체 정발",
        "deal_price": 379000, "original_price": 429000, "discount_percentage": 12,
        "ai_score": 82, "ai_reasoning": "정품 할인",
        "deal_type": "price_drop", "deal_url": "https://www.coupang.com/vp/products/123457",
        "image_url": "https://images.unsplash.com/photo-1578303512597-81e6cc155b3e?w=400&h=300&fit=crop",
        "is_active": True, "expires_at": None,
        "created_at": (now - timedelta(hours=12)).isoformat(),
        "view_count": 4123, "vote_up": 345, "comment_count": 92,
        "shop": {"name": "쿠팡", "slug": "coupang", "logo_url": None, "country": "KR"},
        "category": {"name": "게임/SW", "slug": "games-software"},
    },
    {
        "id": str(uuid.uuid4()),
        "title": "삼성 비스포크 김치냉장고 RQ34C7931AP 327L 1등급",
        "deal_price": 1289000, "original_price": 1690000, "discount_percentage": 24,
        "ai_score": 87, "ai_reasoning": "대형가전 파격 할인",
        "deal_type": "flash_sale", "deal_url": "https://shopping.naver.com/product/123457",
        "image_url": "https://images.unsplash.com/photo-1571175443880-49e1d25b2bc5?w=400&h=300&fit=crop",
        "is_active": True, "expires_at": (now + timedelta(hours=72)).isoformat(),
        "created_at": (now - timedelta(hours=5)).isoformat(),
        "view_count": 1654, "vote_up": 98, "comment_count": 21,
        "shop": {"name": "네이버쇼핑", "slug": "naver", "logo_url": None, "country": "KR"},
        "category": {"name": "가전/TV", "slug": "electronics-tv"},
    },
    {
        "id": str(uuid.uuid4()),
        "title": "스타벅스 기프트카드 5만원권 (즉시발송)",
        "deal_price": 47000, "original_price": 50000, "discount_percentage": 6,
        "ai_score": 75, "ai_reasoning": "상품권 할인",
        "deal_type": "coupon", "deal_url": "https://www.11st.co.kr/products/123457",
        "image_url": "https://images.unsplash.com/photo-1556656793-08538906a9f8?w=400&h=300&fit=crop",
        "is_active": True, "expires_at": None,
        "created_at": (now - timedelta(hours=24)).isoformat(),
        "view_count": 8765, "vote_up": 654, "comment_count": 124,
        "shop": {"name": "11번가", "slug": "11st", "logo_url": None, "country": "KR"},
        "category": {"name": "상품권/쿠폰", "slug": "gift-cards"},
    },
    {
        "id": str(uuid.uuid4()),
        "title": "CJ 백설 햇반 210g x 24개입 (무료배송)",
        "deal_price": 23900, "original_price": 31200, "discount_percentage": 23,
        "ai_score": 79, "ai_reasoning": "생필품 좋은 가격",
        "deal_type": "price_drop", "deal_url": "https://www.ssg.com/item/123457",
        "image_url": "https://images.unsplash.com/photo-1586201375761-83865001e31c?w=400&h=300&fit=crop",
        "is_active": True, "expires_at": None,
        "created_at": (now - timedelta(hours=16)).isoformat(),
        "view_count": 5432, "vote_up": 432, "comment_count": 76,
        "shop": {"name": "SSG.COM", "slug": "ssg", "logo_url": None, "country": "KR"},
        "category": {"name": "생활/식품", "slug": "living-food"},
    },
    {
        "id": str(uuid.uuid4()),
        "title": "샤오미 공기청정기 4 라이트 (관부가세 포함)",
        "deal_price": 89000, "original_price": 159000, "discount_percentage": 44,
        "ai_score": 90, "ai_reasoning": "해외직구 특가",
        "deal_type": "flash_sale", "deal_url": "https://www.aliexpress.com/item/123456",
        "image_url": "https://images.unsplash.com/photo-1585771724684-38269d6639fd?w=400&h=300&fit=crop",
        "is_active": True, "expires_at": (now + timedelta(hours=12)).isoformat(),
        "created_at": (now - timedelta(hours=7)).isoformat(),
        "view_count": 3210, "vote_up": 287, "comment_count": 54,
        "shop": {"name": "알리익스프레스", "slug": "aliexpress", "logo_url": None, "country": "CN"},
        "category": {"name": "가전/TV", "slug": "electronics-tv"},
    },
    {
        "id": str(uuid.uuid4()),
        "title": "AMD 라이젠 7 7800X3D (정품) CPU",
        "deal_price": 489000, "original_price": 599000, "discount_percentage": 18,
        "ai_score": 93, "ai_reasoning": "게이밍 CPU 베스트",
        "deal_type": "price_drop", "deal_url": "https://www.coupang.com/vp/products/123458",
        "image_url": "https://images.unsplash.com/photo-1591799264318-7e6ef8ddb7ea?w=400&h=300&fit=crop",
        "is_active": True, "expires_at": None,
        "created_at": (now - timedelta(hours=10)).isoformat(),
        "view_count": 2876, "vote_up": 198, "comment_count": 43,
        "shop": {"name": "쿠팡", "slug": "coupang", "logo_url": None, "country": "KR"},
        "category": {"name": "PC/하드웨어", "slug": "pc-hardware"},
    },
    # --- International shop deals (Phase 3) ---
    {
        "id": str(uuid.uuid4()),
        "title": "Baldur's Gate 3 - Steam PC 디지털 코드",
        "deal_price": 32450, "original_price": 64900, "discount_percentage": 50,
        "ai_score": 94, "ai_reasoning": "역대 최저가 근접, 50% 할인 대작 게임",
        "deal_type": "flash_sale", "deal_url": "https://store.steampowered.com/app/1086940",
        "image_url": "https://images.unsplash.com/photo-1542751371-adc38448a05e?w=400&h=300&fit=crop",
        "is_active": True, "expires_at": (now + timedelta(hours=48)).isoformat(),
        "created_at": (now - timedelta(hours=1)).isoformat(),
        "view_count": 6543, "vote_up": 521, "comment_count": 134,
        "shop": {"name": "스팀", "slug": "steam", "logo_url": None, "country": "US"},
        "category": {"name": "게임/SW", "slug": "games-software"},
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Elden Ring - Shadow of the Erdtree Edition (Steam)",
        "deal_price": 44910, "original_price": 59900, "discount_percentage": 25,
        "ai_score": 86, "ai_reasoning": "DLC 포함 에디션 역대 최저",
        "deal_type": "price_drop", "deal_url": "https://store.steampowered.com/app/1245620",
        "image_url": "https://images.unsplash.com/photo-1511512578047-dfb367046420?w=400&h=300&fit=crop",
        "is_active": True, "expires_at": None,
        "created_at": (now - timedelta(hours=3)).isoformat(),
        "view_count": 3210, "vote_up": 278, "comment_count": 67,
        "shop": {"name": "스팀", "slug": "steam", "logo_url": None, "country": "US"},
        "category": {"name": "게임/SW", "slug": "games-software"},
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Sony WH-1000XM5 노이즈캔슬링 헤드폰 (아마존 직구)",
        "deal_price": 296000, "original_price": 458000, "discount_percentage": 35,
        "ai_score": 91, "ai_reasoning": "아마존 블랙프라이데이급 할인, 한국보다 16만원 저렴",
        "deal_type": "flash_sale", "deal_url": "https://www.amazon.com/dp/B09XS7JWHH",
        "image_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=400&h=300&fit=crop",
        "is_active": True, "expires_at": (now + timedelta(hours=24)).isoformat(),
        "created_at": (now - timedelta(hours=2)).isoformat(),
        "view_count": 4321, "vote_up": 356, "comment_count": 89,
        "shop": {"name": "아마존", "slug": "amazon", "logo_url": None, "country": "US"},
        "category": {"name": "가전/TV", "slug": "electronics-tv"},
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Apple MacBook Air M3 15인치 (아마존 직구, 관부가세 포함)",
        "deal_price": 1620000, "original_price": 2090000, "discount_percentage": 22,
        "ai_score": 89, "ai_reasoning": "미국 직구 최저가, 국내 대비 47만원 절약",
        "deal_type": "price_drop", "deal_url": "https://www.amazon.com/dp/B0CX23V2ZK",
        "image_url": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=400&h=300&fit=crop",
        "is_active": True, "expires_at": None,
        "created_at": (now - timedelta(hours=5)).isoformat(),
        "view_count": 5432, "vote_up": 445, "comment_count": 112,
        "shop": {"name": "아마존", "slug": "amazon", "logo_url": None, "country": "US"},
        "category": {"name": "노트북/모바일", "slug": "laptop-mobile"},
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Samsung 990 PRO 2TB NVMe M.2 SSD (이베이 직구)",
        "deal_price": 189000, "original_price": 275000, "discount_percentage": 31,
        "ai_score": 88, "ai_reasoning": "2TB NVMe 역대급 가격, 국내보다 8만원 저렴",
        "deal_type": "flash_sale", "deal_url": "https://www.ebay.com/itm/123456",
        "image_url": "https://images.unsplash.com/photo-1597872200969-2b65d56bd16b?w=400&h=300&fit=crop",
        "is_active": True, "expires_at": (now + timedelta(hours=36)).isoformat(),
        "created_at": (now - timedelta(hours=4)).isoformat(),
        "view_count": 2876, "vote_up": 234, "comment_count": 56,
        "shop": {"name": "이베이", "slug": "ebay", "logo_url": None, "country": "US"},
        "category": {"name": "PC/하드웨어", "slug": "pc-hardware"},
    },
    {
        "id": str(uuid.uuid4()),
        "title": "NVIDIA RTX 4070 Ti SUPER 16GB (뉴에그 직구)",
        "deal_price": 945000, "original_price": 1190000, "discount_percentage": 21,
        "ai_score": 87, "ai_reasoning": "뉴에그 한정 세일, 프로모 코드 추가 할인",
        "deal_type": "price_drop", "deal_url": "https://www.newegg.com/p/N82E16814137781",
        "image_url": "https://images.unsplash.com/photo-1591488320449-011701bb6704?w=400&h=300&fit=crop",
        "is_active": True, "expires_at": (now + timedelta(hours=72)).isoformat(),
        "created_at": (now - timedelta(hours=6)).isoformat(),
        "view_count": 3456, "vote_up": 289, "comment_count": 78,
        "shop": {"name": "뉴에그", "slug": "newegg", "logo_url": None, "country": "US"},
        "category": {"name": "PC/하드웨어", "slug": "pc-hardware"},
    },
    # --- Korean scraper shop deals (Phase 4) ---
    {
        "id": str(uuid.uuid4()),
        "title": "삼성 갤럭시 S24 Ultra 256GB 자급제 (옥션 올킬딜)",
        "deal_price": 1199000, "original_price": 1699800, "discount_percentage": 29,
        "ai_score": 90, "ai_reasoning": "자급제 역대 최저가 근접, 올킬딜 한정",
        "deal_type": "flash_sale", "deal_url": "https://www.auction.co.kr/AllKill/123456",
        "image_url": "https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?w=400&h=300&fit=crop",
        "is_active": True, "expires_at": (now + timedelta(hours=6)).isoformat(),
        "created_at": (now - timedelta(hours=1)).isoformat(),
        "view_count": 4567, "vote_up": 378, "comment_count": 95,
        "shop": {"name": "옥션", "slug": "auction", "logo_url": None, "country": "KR"},
        "category": {"name": "노트북/모바일", "slug": "laptop-mobile"},
    },
    {
        "id": str(uuid.uuid4()),
        "title": "삼성 비스포크 그랑데 건조기 DV17B9720CW 17kg 1등급",
        "deal_price": 1098000, "original_price": 1590000, "discount_percentage": 31,
        "ai_score": 88, "ai_reasoning": "건조기 역대 최저가, 인터파크 특가전",
        "deal_type": "price_drop", "deal_url": "https://www.interpark.com/product/123456",
        "image_url": "https://images.unsplash.com/photo-1626806787461-102c1bfaaea1?w=400&h=300&fit=crop",
        "is_active": True, "expires_at": None,
        "created_at": (now - timedelta(hours=3)).isoformat(),
        "view_count": 2345, "vote_up": 187, "comment_count": 43,
        "shop": {"name": "인터파크", "slug": "interpark", "logo_url": None, "country": "KR"},
        "category": {"name": "가전/TV", "slug": "electronics-tv"},
    },
    {
        "id": str(uuid.uuid4()),
        "title": "나이키 에어맥스 97 올블랙 (무신사 단독 세일)",
        "deal_price": 119000, "original_price": 189000, "discount_percentage": 37,
        "ai_score": 83, "ai_reasoning": "무신사 단독 최저가, 인기 컬러웨이",
        "deal_type": "flash_sale", "deal_url": "https://www.musinsa.com/app/goods/123456",
        "image_url": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=400&h=300&fit=crop",
        "is_active": True, "expires_at": (now + timedelta(hours=48)).isoformat(),
        "created_at": (now - timedelta(hours=5)).isoformat(),
        "view_count": 6789, "vote_up": 534, "comment_count": 156,
        "shop": {"name": "무신사", "slug": "musinsa", "logo_url": None, "country": "KR"},
        "category": {"name": "생활/식품", "slug": "living-food"},
    },
    {
        "id": str(uuid.uuid4()),
        "title": "LG 올레드 TV OLED65C4KNA 65인치 4K (하이마트 광세일)",
        "deal_price": 2190000, "original_price": 3290000, "discount_percentage": 33,
        "ai_score": 92, "ai_reasoning": "OLED TV 역대급 할인, 광세일 한정가",
        "deal_type": "clearance", "deal_url": "https://www.e-himart.co.kr/app/product/123456",
        "image_url": "https://images.unsplash.com/photo-1593359677879-a4bb92f829d1?w=400&h=300&fit=crop",
        "is_active": True, "expires_at": (now + timedelta(hours=72)).isoformat(),
        "created_at": (now - timedelta(hours=2)).isoformat(),
        "view_count": 3456, "vote_up": 289, "comment_count": 78,
        "shop": {"name": "하이마트", "slug": "himart", "logo_url": None, "country": "KR"},
        "category": {"name": "가전/TV", "slug": "electronics-tv"},
    },
    {
        "id": str(uuid.uuid4()),
        "title": "빈폴 키즈 패딩 점퍼 겨울 아우터 (SSF 시즌오프)",
        "deal_price": 89000, "original_price": 199000, "discount_percentage": 55,
        "ai_score": 81, "ai_reasoning": "시즌오프 55% 할인, 유아동복 베스트셀러",
        "deal_type": "clearance", "deal_url": "https://www.ssfshop.com/product/123456",
        "image_url": "https://images.unsplash.com/photo-1604695573706-53170668f6a6?w=400&h=300&fit=crop",
        "is_active": True, "expires_at": None,
        "created_at": (now - timedelta(hours=8)).isoformat(),
        "view_count": 1234, "vote_up": 98, "comment_count": 34,
        "shop": {"name": "SSF샵", "slug": "ssf", "logo_url": None, "country": "KR"},
        "category": {"name": "생활/식품", "slug": "living-food"},
    },
]

TRENDING_KEYWORDS = [
    {"keyword": "애플 에어팟", "search_count": 1523, "rank": 1},
    {"keyword": "삼성 갤럭시", "search_count": 1289, "rank": 2},
    {"keyword": "LG 그램", "search_count": 987, "rank": 3},
    {"keyword": "다이슨 청소기", "search_count": 876, "rank": 4},
    {"keyword": "아이패드", "search_count": 754, "rank": 5},
    {"keyword": "닌텐도 스위치", "search_count": 698, "rank": 6},
    {"keyword": "라이젠 7800X3D", "search_count": 543, "rank": 7},
    {"keyword": "에어프라이어", "search_count": 432, "rank": 8},
    {"keyword": "로지텍 마우스", "search_count": 387, "rank": 9},
    {"keyword": "김치냉장고", "search_count": 321, "rank": 10},
]

# --- Helper functions ---

def _filter_deals(
    deals: list,
    category: Optional[str] = None,
    shop: Optional[str] = None,
    min_discount: Optional[float] = None,
    deal_type: Optional[str] = None,
    query: Optional[str] = None,
) -> list:
    result = deals[:]
    if category:
        result = [d for d in result if d.get("category", {}).get("slug") == category]
    if shop:
        shop_slugs = shop.split(",")
        result = [d for d in result if d.get("shop", {}).get("slug") in shop_slugs]
    if min_discount is not None:
        result = [d for d in result if (d.get("discount_percentage") or 0) >= min_discount]
    if deal_type:
        result = [d for d in result if d.get("deal_type") == deal_type]
    if query:
        q = query.lower()
        result = [d for d in result if q in d["title"].lower()]
    return result


def _sort_deals(deals: list, sort_by: str) -> list:
    if sort_by == "score":
        return sorted(deals, key=lambda d: d.get("ai_score") or 0, reverse=True)
    elif sort_by == "discount":
        return sorted(deals, key=lambda d: d.get("discount_percentage") or 0, reverse=True)
    elif sort_by == "views":
        return sorted(deals, key=lambda d: d.get("view_count") or 0, reverse=True)
    else:  # newest
        return sorted(deals, key=lambda d: d.get("created_at", ""), reverse=True)


def _paginate(items: list, page: int, limit: int):
    total = len(items)
    start = (page - 1) * limit
    end = start + limit
    return items[start:end], total


# --- API Endpoints ---

@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "database": "mock", "services": {"database": "mock", "redis": "mock"}}


@app.get("/api/v1/deals")
async def list_deals(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    shop: Optional[str] = None,
    sort_by: str = Query("newest"),
    min_discount: Optional[float] = None,
    deal_type: Optional[str] = None,
):
    filtered = _filter_deals(DEALS, category=category, shop=shop, min_discount=min_discount, deal_type=deal_type)
    sorted_deals = _sort_deals(filtered, sort_by)
    page_deals, total = _paginate(sorted_deals, page, limit)
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    return {
        "status": "success",
        "data": page_deals,
        "meta": {"page": page, "limit": limit, "total": total, "total_pages": total_pages},
    }


@app.get("/api/v1/deals/top")
async def top_deals(
    limit: int = Query(20, ge=1, le=50),
    category: Optional[str] = None,
):
    filtered = _filter_deals(DEALS, category=category)
    sorted_deals = _sort_deals(filtered, "score")[:limit]
    return {"status": "success", "data": sorted_deals}


@app.get("/api/v1/deals/{deal_id}")
async def get_deal(deal_id: str):
    deal = next((d for d in DEALS if d["id"] == deal_id), None)
    if not deal:
        return {"status": "error", "error": {"code": "not_found", "message": "Deal not found"}}
    # Add mock price history
    detail = {**deal, "description": None, "starts_at": None, "vote_down": 5, "price_history": [
        {"price": deal["original_price"], "recorded_at": (now - timedelta(days=30)).isoformat()},
        {"price": deal["original_price"] * 0.95, "recorded_at": (now - timedelta(days=20)).isoformat()},
        {"price": deal["original_price"] * 0.90, "recorded_at": (now - timedelta(days=10)).isoformat()},
        {"price": deal["deal_price"], "recorded_at": now.isoformat()},
    ]}
    return {"status": "success", "data": detail}


@app.get("/api/v1/categories")
async def list_categories():
    return {"status": "success", "data": CATEGORIES}


@app.get("/api/v1/categories/{slug}/deals")
async def category_deals(
    slug: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("newest"),
):
    filtered = _filter_deals(DEALS, category=slug)
    sorted_deals = _sort_deals(filtered, sort_by)
    page_deals, total = _paginate(sorted_deals, page, limit)
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    return {
        "status": "success",
        "data": page_deals,
        "meta": {"page": page, "limit": limit, "total": total, "total_pages": total_pages},
    }


@app.get("/api/v1/shops")
async def list_shops(active_only: bool = True):
    shops = SHOPS if not active_only else [s for s in SHOPS if s["is_active"]]
    return {"status": "success", "data": shops}


@app.get("/api/v1/shops/{slug}")
async def get_shop(slug: str):
    shop = next((s for s in SHOPS if s["slug"] == slug), None)
    if not shop:
        return {"status": "error", "error": {"code": "not_found", "message": "Shop not found"}}
    return {"status": "success", "data": shop}


@app.get("/api/v1/shops/{slug}/deals")
async def shop_deals(
    slug: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("newest"),
):
    filtered = _filter_deals(DEALS, shop=slug)
    sorted_deals = _sort_deals(filtered, sort_by)
    page_deals, total = _paginate(sorted_deals, page, limit)
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    return {
        "status": "success",
        "data": page_deals,
        "meta": {"page": page, "limit": limit, "total": total, "total_pages": total_pages},
    }


@app.get("/api/v1/search")
async def search(
    q: str = Query("", min_length=1),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    shop: Optional[str] = None,
    sort_by: str = Query("relevance"),
):
    filtered = _filter_deals(DEALS, category=category, shop=shop, query=q)
    sort_key = "score" if sort_by == "relevance" else sort_by
    sorted_deals = _sort_deals(filtered, sort_key)
    page_deals, total = _paginate(sorted_deals, page, limit)
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    return {
        "status": "success",
        "data": page_deals,
        "meta": {"page": page, "limit": limit, "total": total, "total_pages": total_pages},
    }


@app.get("/api/v1/trending")
async def trending(limit: int = Query(10, ge=1, le=50)):
    return {"status": "success", "data": TRENDING_KEYWORDS[:limit]}


@app.get("/api/v1/trending/recent")
async def recent_searches(limit: int = Query(10, ge=1, le=50)):
    recent = [
        {"keyword": kw["keyword"], "search_count": kw["search_count"], "last_searched_at": now.isoformat()}
        for kw in TRENDING_KEYWORDS[:limit]
    ]
    return {"status": "success", "data": recent}


# --- Mock comments storage ---
MOCK_COMMENTS = {}  # deal_id -> list of comments
MOCK_USER_VOTES = {}  # f"{user_id}:{deal_id}" -> vote_type


@app.post("/api/v1/auth/register")
async def register(body: RegisterBody):
    if body.email in MOCK_USERS_BY_EMAIL:
        raise HTTPException(status_code=400, detail="이미 사용 중인 이메일입니다")
    user_id = str(uuid.uuid4())
    user = {
        "id": user_id,
        "email": body.email,
        "username": body.username,
        "is_active": True,
        "created_at": now.isoformat(),
    }
    token = _mock_token(user_id)
    MOCK_USERS[token] = user
    MOCK_USERS_BY_EMAIL[body.email] = {**user, "password": body.password, "token": token}
    return {
        "status": "success",
        "data": {
            "user": user,
            "token": {"access_token": token, "token_type": "bearer"},
        },
    }


@app.post("/api/v1/auth/login")
async def login(body: LoginBody):
    stored = MOCK_USERS_BY_EMAIL.get(body.email)
    if not stored or stored["password"] != body.password:
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다")
    user = {k: v for k, v in stored.items() if k not in ("password", "token")}
    return {
        "status": "success",
        "data": {
            "user": user,
            "token": {"access_token": stored["token"], "token_type": "bearer"},
        },
    }


class ResetPasswordBody(BaseModel):
    email: str


@app.post("/api/v1/auth/reset-password")
async def reset_password(body: ResetPasswordBody):
    return {
        "status": "success",
        "data": {"message": "비밀번호 재설정 링크가 이메일로 전송되었습니다"},
    }


@app.get("/api/v1/auth/me")
async def get_me(authorization: Optional[str] = Header(None)):
    user = _get_mock_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    return {"status": "success", "data": user}


@app.get("/api/v1/deals/{deal_id}/comments")
async def list_comments(deal_id: str):
    comments = MOCK_COMMENTS.get(deal_id, [])
    # Filter top-level, attach replies
    top_level = [c for c in comments if not c.get("parent_id") and not c.get("is_deleted")]
    for c in top_level:
        c["replies"] = [r for r in comments if r.get("parent_id") == c["id"] and not r.get("is_deleted")]
    return {"status": "success", "data": top_level}


@app.post("/api/v1/deals/{deal_id}/comments")
async def create_comment(deal_id: str, body: CommentBody, authorization: Optional[str] = Header(None)):
    user = _get_mock_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    comment = {
        "id": str(uuid.uuid4()),
        "deal_id": deal_id,
        "user": {"id": user["id"], "username": user["username"]},
        "parent_id": body.parent_id,
        "content": body.content,
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "replies": [],
    }
    if deal_id not in MOCK_COMMENTS:
        MOCK_COMMENTS[deal_id] = []
    MOCK_COMMENTS[deal_id].append(comment)
    # Update deal comment count
    deal = next((d for d in DEALS if d["id"] == deal_id), None)
    if deal:
        deal["comment_count"] = deal.get("comment_count", 0) + 1
    return {"status": "success", "data": comment}


@app.delete("/api/v1/deals/{deal_id}/comments/{comment_id}")
async def delete_comment(deal_id: str, comment_id: str, authorization: Optional[str] = Header(None)):
    user = _get_mock_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    comments = MOCK_COMMENTS.get(deal_id, [])
    comment = next((c for c in comments if c["id"] == comment_id), None)
    if not comment or comment["user"]["id"] != user["id"]:
        raise HTTPException(status_code=404, detail="댓글을 찾을 수 없습니다")
    comment["is_deleted"] = True
    comment["content"] = "삭제된 댓글입니다"
    return {"status": "success", "data": {"deleted": True}}


@app.get("/api/v1/deals/{deal_id}/vote")
async def get_vote_status(deal_id: str, authorization: Optional[str] = Header(None)):
    user = _get_mock_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    vote_key = f"{user['id']}:{deal_id}"
    user_vote = MOCK_USER_VOTES.get(vote_key)
    return {"status": "success", "data": {"user_vote": user_vote}}


@app.post("/api/v1/deals/{deal_id}/vote")
async def vote_deal(deal_id: str, body: VoteBody, authorization: Optional[str] = Header(None)):
    user = _get_mock_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    deal = next((d for d in DEALS if d["id"] == deal_id), None)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    vote_key = f"{user['id']}:{deal_id}"
    existing = MOCK_USER_VOTES.get(vote_key)
    user_vote = None

    if existing == body.vote_type:
        # Toggle off
        if body.vote_type == "up":
            deal["vote_up"] = max(0, deal.get("vote_up", 0) - 1)
        else:
            deal["vote_down"] = max(0, deal.get("vote_down", 0) - 1)
        del MOCK_USER_VOTES[vote_key]
    elif existing:
        # Switch
        if existing == "up":
            deal["vote_up"] = max(0, deal.get("vote_up", 0) - 1)
            deal["vote_down"] = deal.get("vote_down", 0) + 1
        else:
            deal["vote_down"] = max(0, deal.get("vote_down", 0) - 1)
            deal["vote_up"] = deal.get("vote_up", 0) + 1
        MOCK_USER_VOTES[vote_key] = body.vote_type
        user_vote = body.vote_type
    else:
        # New vote
        if body.vote_type == "up":
            deal["vote_up"] = deal.get("vote_up", 0) + 1
        else:
            deal["vote_down"] = deal.get("vote_down", 0) + 1
        MOCK_USER_VOTES[vote_key] = body.vote_type
        user_vote = body.vote_type

    return {
        "status": "success",
        "data": {
            "deal_id": deal_id,
            "vote_up": deal.get("vote_up", 0),
            "vote_down": deal.get("vote_down", 0),
            "user_vote": user_vote,
        },
    }


class MigrateFixBody(BaseModel):
    api_key: str


@app.post("/api/v1/ingest/migrate-fix")
async def migrate_fix(body: MigrateFixBody):
    return {
        "status": "success",
        "images_fixed_products": 0,
        "images_fixed_deals": 0,
        "categories_fixed_products": 0,
        "categories_fixed_deals": 0,
    }


@app.get("/api/v1/alerts")
async def list_alerts(authorization: Optional[str] = Header(None)):
    user = _get_mock_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    return {"status": "success", "data": []}


@app.get("/")
async def root():
    return {
        "name": "DealHawk Mock API",
        "version": "0.1.0-mock",
        "description": "Mock server for local development (no DB required)",
        "docs": "/docs",
        "health": "/api/v1/health",
    }
