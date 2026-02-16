"""Comprehensive test suite for DealHawk backend services.

Tests cover:
- Product service (CRUD, price history, upsert)
- Deal service (CRUD, filtering, voting)
- Schema validation
- Database operations with async patterns
"""

import pytest
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from jsonschema import validate, ValidationError
from unittest.mock import AsyncMock, MagicMock, patch

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.models import (
    Shop, Category, Product, Deal, PriceHistory,
    SearchKeyword, ScraperJob
)
from app.schemas import (
    ProductResponse, ProductDetailResponse, DealResponse,
    DealDetailResponse, ShopResponse, CategoryResponse
)
from app.services.product_service import ProductService
from app.services.deal_service import DealService
from app.scrapers.base import NormalizedProduct, NormalizedDeal


# ============================================================================
# FIXTURES
# ============================================================================

@pytest_asyncio.fixture
async def test_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with SessionLocal() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def sample_shop(test_db: AsyncSession) -> Shop:
    """Create a sample shop for testing."""
    shop = Shop(
        name="테스트 쇼핑몰",
        name_en="Test Shop",
        slug="test-shop",
        logo_url="https://example.com/logo.png",
        base_url="https://example.com",
        adapter_type="api",
        is_active=True,
        scrape_interval_minutes=60,
        country="KR",
        currency="KRW",
    )
    test_db.add(shop)
    await test_db.commit()
    await test_db.refresh(shop)
    return shop


@pytest_asyncio.fixture
async def sample_category(test_db: AsyncSession) -> Category:
    """Create a sample category for testing."""
    category = Category(
        name="전자제품",
        name_en="Electronics",
        slug="electronics",
        icon="cpu",
        sort_order=1,
    )
    test_db.add(category)
    await test_db.commit()
    await test_db.refresh(category)
    return category


@pytest_asyncio.fixture
async def sample_product(
    test_db: AsyncSession,
    sample_shop: Shop,
    sample_category: Category
) -> Product:
    """Create a sample product for testing."""
    product = Product(
        external_id="test-prod-001",
        shop_id=sample_shop.id,
        category_id=sample_category.id,
        title="테스트 상품",
        original_price=Decimal("100000.00"),
        current_price=Decimal("50000.00"),
        currency="KRW",
        image_url="https://example.com/image.jpg",
        product_url="https://example.com/product/test",
        brand="TestBrand",
        is_active=True,
    )
    test_db.add(product)
    await test_db.commit()
    await test_db.refresh(product)
    return product


# ============================================================================
# TESTS: PRODUCT SERVICE
# ============================================================================

class TestProductService:
    """Tests for ProductService."""

    async def test_upsert_product_create_new(
        self,
        test_db: AsyncSession,
        sample_shop: Shop,
        sample_category: Category
    ):
        """Test creating a new product via upsert."""
        service = ProductService(test_db)

        normalized = NormalizedProduct(
            external_id="new-product-001",
            title="새로운 상품",
            current_price=Decimal("75000.00"),
            original_price=Decimal("100000.00"),
            product_url="https://example.com/new",
            currency="KRW",
            image_url="https://example.com/new.jpg",
            brand="NewBrand",
            category_hint="electronics",
        )

        product = await service.upsert_product(
            shop_id=sample_shop.id,
            normalized=normalized,
            category_id=sample_category.id,
        )

        assert product.id is not None
        assert product.external_id == "new-product-001"
        assert product.title == "새로운 상품"
        assert product.current_price == Decimal("75000.00")
        assert product.shop_id == sample_shop.id
        assert product.is_active is True

    async def test_upsert_product_update_existing(
        self,
        test_db: AsyncSession,
        sample_shop: Shop,
        sample_product: Product
    ):
        """Test updating an existing product via upsert."""
        service = ProductService(test_db)

        normalized = NormalizedProduct(
            external_id=sample_product.external_id,
            title="업데이트된 상품",
            current_price=Decimal("45000.00"),
            original_price=Decimal("95000.00"),
            product_url="https://example.com/product/test",
            currency="KRW",
        )

        product = await service.upsert_product(
            shop_id=sample_shop.id,
            normalized=normalized,
        )

        assert product.id == sample_product.id  # Same product ID
        assert product.title == "업데이트된 상품"
        assert product.current_price == Decimal("45000.00")

    async def test_upsert_product_records_price_history(
        self,
        test_db: AsyncSession,
        sample_shop: Shop,
        sample_category: Category
    ):
        """Test that upsert creates price history entries."""
        service = ProductService(test_db)

        normalized = NormalizedProduct(
            external_id="price-test-001",
            title="가격 테스트",
            current_price=Decimal("10000.00"),
            product_url="https://example.com/test",
        )

        product = await service.upsert_product(
            shop_id=sample_shop.id,
            normalized=normalized,
            category_id=sample_category.id,
        )

        # Verify price history was created
        history = await service.get_price_history(product.id)
        assert len(history) == 1
        assert history[0].price == Decimal("10000.00")

    async def test_get_product_by_id(
        self,
        test_db: AsyncSession,
        sample_product: Product
    ):
        """Test retrieving a product by ID."""
        service = ProductService(test_db)
        product = await service.get_product_by_id(sample_product.id)

        assert product is not None
        assert product.id == sample_product.id
        assert product.title == sample_product.title

    async def test_get_product_by_id_not_found(
        self,
        test_db: AsyncSession
    ):
        """Test retrieving non-existent product returns None."""
        service = ProductService(test_db)
        product = await service.get_product_by_id(uuid4())

        assert product is None

    async def test_get_products_with_pagination(
        self,
        test_db: AsyncSession,
        sample_shop: Shop,
        sample_category: Category
    ):
        """Test paginated product listing."""
        service = ProductService(test_db)

        # Create multiple products
        for i in range(5):
            product = Product(
                external_id=f"product-{i}",
                shop_id=sample_shop.id,
                category_id=sample_category.id,
                title=f"상품 {i}",
                current_price=Decimal("10000.00"),
                product_url=f"https://example.com/{i}",
                is_active=True,
            )
            test_db.add(product)

        await test_db.commit()

        # Test pagination
        products, total = await service.get_products(page=1, limit=2)

        assert len(products) == 2
        assert total == 5

    async def test_get_products_filter_by_shop(
        self,
        test_db: AsyncSession,
        sample_shop: Shop,
        sample_category: Category
    ):
        """Test filtering products by shop."""
        service = ProductService(test_db)

        # Create two shops
        shop2 = Shop(
            name="다른 쇼핑몰",
            name_en="Other Shop",
            slug="other-shop",
            base_url="https://other.com",
            is_active=True,
        )
        test_db.add(shop2)
        await test_db.commit()

        # Create products in each shop
        for shop in [sample_shop, shop2]:
            product = Product(
                external_id=f"prod-{shop.slug}",
                shop_id=shop.id,
                title=f"상품 in {shop.name}",
                current_price=Decimal("10000.00"),
                product_url=f"https://example.com/prod",
                is_active=True,
            )
            test_db.add(product)

        await test_db.commit()

        # Filter by shop
        products, total = await service.get_products(shop_id=sample_shop.id)

        assert total == 1
        assert products[0].shop_id == sample_shop.id

    async def test_get_price_history(
        self,
        test_db: AsyncSession,
        sample_product: Product
    ):
        """Test retrieving price history for a product."""
        service = ProductService(test_db)

        # Create price history entries
        now = datetime.now(timezone.utc)
        for i in range(3):
            entry = PriceHistory(
                product_id=sample_product.id,
                price=Decimal("50000.00") - Decimal(i * 1000),
                currency="KRW",
                recorded_at=now - timedelta(days=i),
            )
            test_db.add(entry)

        await test_db.commit()

        history = await service.get_price_history(sample_product.id, days=30)

        assert len(history) == 3
        # Verify ordered chronologically
        assert history[0].recorded_at < history[1].recorded_at

    async def test_get_price_statistics(
        self,
        test_db: AsyncSession,
        sample_product: Product
    ):
        """Test computing price statistics."""
        service = ProductService(test_db)

        # Create price history
        prices = [100000, 95000, 90000, 85000, 80000]
        now = datetime.now(timezone.utc)

        for i, price in enumerate(prices):
            entry = PriceHistory(
                product_id=sample_product.id,
                price=Decimal(str(price)),
                currency="KRW",
                recorded_at=now - timedelta(days=len(prices) - i - 1),
            )
            test_db.add(entry)

        await test_db.commit()

        stats = await service.get_price_statistics(sample_product.id, days=30)

        assert stats is not None
        assert stats["min_price"] == 80000
        assert stats["max_price"] == 100000
        assert stats["current_price"] == 80000

    async def test_deactivate_stale_products(
        self,
        test_db: AsyncSession,
        sample_shop: Shop
    ):
        """Test deactivating stale products."""
        service = ProductService(test_db)

        # Create fresh and stale products
        fresh = Product(
            external_id="fresh",
            shop_id=sample_shop.id,
            title="신규",
            current_price=Decimal("10000"),
            product_url="https://example.com/fresh",
            is_active=True,
            last_scraped_at=datetime.now(timezone.utc),
        )

        stale = Product(
            external_id="stale",
            shop_id=sample_shop.id,
            title="오래됨",
            current_price=Decimal("10000"),
            product_url="https://example.com/stale",
            is_active=True,
            last_scraped_at=datetime.now(timezone.utc) - timedelta(days=31),
        )

        test_db.add_all([fresh, stale])
        await test_db.commit()

        # Deactivate stale
        count = await service.deactivate_stale_products(days=30)

        assert count == 1

        # Verify stale is deactivated
        await test_db.refresh(stale)
        assert stale.is_active is False


# ============================================================================
# TESTS: DEAL SERVICE
# ============================================================================

class TestDealService:
    """Tests for DealService."""

    async def test_get_deals_pagination(
        self,
        test_db: AsyncSession,
        sample_shop: Shop,
        sample_product: Product
    ):
        """Test deal listing with pagination."""
        service = DealService(test_db)

        # Create multiple deals
        for i in range(5):
            deal = Deal(
                product_id=sample_product.id,
                shop_id=sample_shop.id,
                deal_price=Decimal("50000.00"),
                title=f"특가 {i}",
                deal_url="https://example.com/deal",
                deal_type="price_drop",
                is_active=True,
            )
            test_db.add(deal)

        await test_db.commit()

        deals, total = await service.get_deals(page=1, limit=2)

        assert len(deals) == 2
        assert total == 5

    async def test_get_deals_filter_by_category(
        self,
        test_db: AsyncSession,
        sample_shop: Shop,
        sample_product: Product,
        sample_category: Category
    ):
        """Test filtering deals by category."""
        service = DealService(test_db)

        # Create deal with category
        deal = Deal(
            product_id=sample_product.id,
            shop_id=sample_shop.id,
            category_id=sample_category.id,
            deal_price=Decimal("50000.00"),
            title="카테고리 특가",
            deal_url="https://example.com/deal",
            is_active=True,
        )
        test_db.add(deal)
        await test_db.commit()

        # Filter by category
        deals, total = await service.get_deals(category_slug=sample_category.slug)

        assert len(deals) == 1
        assert deals[0].category_id == sample_category.id

    async def test_get_top_deals(
        self,
        test_db: AsyncSession,
        sample_shop: Shop,
        sample_product: Product
    ):
        """Test retrieving top AI-scored deals."""
        service = DealService(test_db)

        # Create deals with scores
        scores = [80, 90, 70, 85]
        for score in scores:
            deal = Deal(
                product_id=sample_product.id,
                shop_id=sample_shop.id,
                deal_price=Decimal("50000.00"),
                title=f"점수 {score}",
                deal_url="https://example.com/deal",
                ai_score=Decimal(str(score)),
                is_active=True,
            )
            test_db.add(deal)

        await test_db.commit()

        top = await service.get_top_deals(limit=2)

        assert len(top) == 2
        # Should be sorted by score descending
        assert float(top[0].ai_score) >= float(top[1].ai_score)

    async def test_get_deal_by_id_increments_view_count(
        self,
        test_db: AsyncSession,
        sample_shop: Shop,
        sample_product: Product
    ):
        """Test that viewing a deal increments view count."""
        service = DealService(test_db)

        deal = Deal(
            product_id=sample_product.id,
            shop_id=sample_shop.id,
            deal_price=Decimal("50000.00"),
            title="조회수 테스트",
            deal_url="https://example.com/deal",
            is_active=True,
            view_count=0,
        )
        test_db.add(deal)
        await test_db.commit()

        # Get deal (should increment views)
        retrieved = await service.get_deal_by_id(deal.id)

        assert retrieved is not None
        assert retrieved.view_count == 1

    async def test_vote_deal_upvote(
        self,
        test_db: AsyncSession,
        sample_shop: Shop,
        sample_product: Product
    ):
        """Test upvoting a deal."""
        service = DealService(test_db)

        deal = Deal(
            product_id=sample_product.id,
            shop_id=sample_shop.id,
            deal_price=Decimal("50000.00"),
            title="투표 테스트",
            deal_url="https://example.com/deal",
            is_active=True,
        )
        test_db.add(deal)
        await test_db.commit()

        # Upvote
        updated = await service.vote_deal(deal.id, "up")

        assert updated is not None
        assert updated.vote_up == 1
        assert updated.vote_down == 0

    async def test_vote_deal_downvote(
        self,
        test_db: AsyncSession,
        sample_shop: Shop,
        sample_product: Product
    ):
        """Test downvoting a deal."""
        service = DealService(test_db)

        deal = Deal(
            product_id=sample_product.id,
            shop_id=sample_shop.id,
            deal_price=Decimal("50000.00"),
            title="투표 테스트",
            deal_url="https://example.com/deal",
            is_active=True,
        )
        test_db.add(deal)
        await test_db.commit()

        # Downvote
        updated = await service.vote_deal(deal.id, "down")

        assert updated is not None
        assert updated.vote_down == 1
        assert updated.vote_up == 0

    async def test_expire_stale_deals(
        self,
        test_db: AsyncSession,
        sample_shop: Shop,
        sample_product: Product
    ):
        """Test expiring stale deals."""
        service = DealService(test_db)

        now = datetime.now(timezone.utc)

        # Active deal
        active = Deal(
            product_id=sample_product.id,
            shop_id=sample_shop.id,
            deal_price=Decimal("50000.00"),
            title="활성 특가",
            deal_url="https://example.com/deal",
            is_active=True,
            expires_at=now + timedelta(days=1),
        )

        # Expired deal
        expired = Deal(
            product_id=sample_product.id,
            shop_id=sample_shop.id,
            deal_price=Decimal("50000.00"),
            title="만료된 특가",
            deal_url="https://example.com/deal",
            is_active=True,
            expires_at=now - timedelta(hours=1),
        )

        test_db.add_all([active, expired])
        await test_db.commit()

        # Expire stale
        count = await service.expire_stale_deals()

        assert count == 1

        # Verify expired is marked as expired
        await test_db.refresh(expired)
        assert expired.is_active is False
        assert expired.is_expired is True


# ============================================================================
# TESTS: SCHEMA VALIDATION
# ============================================================================

class TestSchemaValidation:
    """Tests for Pydantic schema validation."""

    def test_product_response_schema(self):
        """Test ProductResponse schema validation."""
        valid_data = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "title": "테스트 상품",
            "original_price": 100000.00,
            "current_price": 50000.00,
            "currency": "KRW",
            "image_url": "https://example.com/img.jpg",
            "product_url": "https://example.com/product",
            "brand": "TestBrand",
            "external_id": "ext-001",
        }

        schema = ProductResponse(**valid_data)
        assert schema.title == "테스트 상품"
        assert schema.current_price == 50000.00

    def test_deal_response_schema(self):
        """Test DealResponse schema validation."""
        valid_data = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "title": "특가",
            "deal_price": 50000.00,
            "original_price": 100000.00,
            "discount_percentage": 50.0,
            "ai_score": 85.0,
            "ai_reasoning": "가성비 좋은 상품",
            "deal_type": "price_drop",
            "deal_url": "https://example.com/deal",
            "image_url": "https://example.com/img.jpg",
            "is_active": True,
            "expires_at": None,
            "created_at": datetime.now(timezone.utc),
            "view_count": 100,
            "vote_up": 50,
            "comment_count": 10,
            "shop": {
                "name": "테스트 쇼핑몰",
                "slug": "test",
                "logo_url": None,
                "country": "KR",
            },
            "category": None,
        }

        schema = DealResponse(**valid_data)
        assert schema.title == "특가"
        assert schema.ai_score == 85.0


# ============================================================================
# TESTS: NORMALIZED DATA STRUCTURES
# ============================================================================

class TestNormalizedDataStructures:
    """Tests for scraper normalized data classes."""

    def test_normalized_product_validation(self):
        """Test NormalizedProduct data validation."""
        product = NormalizedProduct(
            external_id="naver-001",
            title="네이버 특가",
            current_price=Decimal("50000"),
            product_url="https://shopping.naver.com/product/123",
            original_price=Decimal("100000"),
            image_url="https://shopping-phinf.pstatic.net/img.jpg",
            brand="TestBrand",
        )

        assert product.external_id == "naver-001"
        assert product.current_price == Decimal("50000")

    def test_normalized_product_invalid_price_negative(self):
        """Test NormalizedProduct rejects negative prices."""
        with pytest.raises(ValueError, match="current_price must be non-negative"):
            NormalizedProduct(
                external_id="invalid",
                title="테스트",
                current_price=Decimal("-100"),
                product_url="https://example.com",
            )

    def test_normalized_product_invalid_missing_required_fields(self):
        """Test NormalizedProduct requires external_id and title."""
        with pytest.raises(ValueError, match="external_id is required"):
            NormalizedProduct(
                external_id="",
                title="테스트",
                current_price=Decimal("100"),
                product_url="https://example.com",
            )

    def test_normalized_deal_validation(self):
        """Test NormalizedDeal data validation."""
        product = NormalizedProduct(
            external_id="prod-001",
            title="상품",
            current_price=Decimal("50000"),
            product_url="https://example.com",
        )

        deal = NormalizedDeal(
            product=product,
            deal_price=Decimal("50000"),
            title="특가",
            deal_url="https://example.com/deal",
            deal_type="price_drop",
        )

        assert deal.product.external_id == "prod-001"
        assert deal.deal_type == "price_drop"

    def test_normalized_deal_invalid_deal_type(self):
        """Test NormalizedDeal rejects invalid deal types."""
        product = NormalizedProduct(
            external_id="prod-001",
            title="상품",
            current_price=Decimal("50000"),
            product_url="https://example.com",
        )

        with pytest.raises(ValueError, match="Invalid deal_type"):
            NormalizedDeal(
                product=product,
                deal_price=Decimal("50000"),
                title="특가",
                deal_url="https://example.com/deal",
                deal_type="invalid_type",
            )


# ============================================================================
# TESTS: ERROR HANDLING
# ============================================================================

class TestErrorHandling:
    """Tests for error handling and edge cases."""

    async def test_product_service_handles_nonexistent_product(
        self, test_db: AsyncSession
    ):
        """Test service handles missing product gracefully."""
        service = ProductService(test_db)
        product = await service.get_product_by_id(uuid4())

        assert product is None

    async def test_deal_service_handles_invalid_vote_type(
        self,
        test_db: AsyncSession,
        sample_shop: Shop,
        sample_product: Product
    ):
        """Test service rejects invalid vote types."""
        service = DealService(test_db)

        deal = Deal(
            product_id=sample_product.id,
            shop_id=sample_shop.id,
            deal_price=Decimal("50000"),
            title="테스트",
            deal_url="https://example.com",
            is_active=True,
        )
        test_db.add(deal)
        await test_db.commit()

        with pytest.raises(ValueError, match="vote_type must be"):
            await service.vote_deal(deal.id, "invalid")


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
