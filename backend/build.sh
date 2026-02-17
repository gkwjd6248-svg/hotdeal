#!/usr/bin/env bash
set -e

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Running database migrations..."
python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings
from app.models.base import Base

# Import all models so they register with Base.metadata
from app.models import shop, category, product, price_history, deal, scraper_job, search_keyword, user, comment, user_vote, price_alert

async def init_db():
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print('Database tables created/verified.')

asyncio.run(init_db())
"

echo "Seeding initial data..."
python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from app.config import settings
from app.models.shop import Shop
from app.models.category import Category
import uuid

async def seed():
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Check if already seeded
        result = await session.execute(select(Shop).limit(1))
        if result.scalar_one_or_none():
            print('Data already seeded, skipping.')
            await engine.dispose()
            return

        # Seed shops
        shops = [
            Shop(id=uuid.uuid4(), name='네이버 쇼핑', name_en='Naver Shopping', slug='naver', base_url='https://shopping.naver.com', adapter_type='api', is_active=True, scrape_interval_minutes=30, country='KR', currency='KRW'),
            Shop(id=uuid.uuid4(), name='스팀', name_en='Steam', slug='steam', base_url='https://store.steampowered.com', adapter_type='api', is_active=True, scrape_interval_minutes=60, country='US', currency='USD'),
            Shop(id=uuid.uuid4(), name='쿠팡', name_en='Coupang', slug='coupang', base_url='https://www.coupang.com', adapter_type='api', is_active=False, scrape_interval_minutes=30, country='KR', currency='KRW'),
            Shop(id=uuid.uuid4(), name='11번가', name_en='11st', slug='11st', base_url='https://www.11st.co.kr', adapter_type='api', is_active=False, scrape_interval_minutes=30, country='KR', currency='KRW'),
        ]
        session.add_all(shops)

        # Seed categories
        categories = [
            Category(id=uuid.uuid4(), name='PC/하드웨어', slug='pc-hardware', icon='Monitor', sort_order=1),
            Category(id=uuid.uuid4(), name='노트북/모바일', slug='laptop-mobile', icon='Laptop', sort_order=2),
            Category(id=uuid.uuid4(), name='게임/SW', slug='games-software', icon='Gamepad2', sort_order=3),
            Category(id=uuid.uuid4(), name='가전/TV', slug='electronics-tv', icon='Tv', sort_order=4),
            Category(id=uuid.uuid4(), name='생활/식품', slug='living-food', icon='ShoppingCart', sort_order=5),
            Category(id=uuid.uuid4(), name='상품권/쿠폰', slug='voucher-coupon', icon='Ticket', sort_order=6),
        ]
        session.add_all(categories)

        await session.commit()
        print(f'Seeded {len(shops)} shops and {len(categories)} categories.')

    await engine.dispose()

asyncio.run(seed())
"

echo "Build complete!"
