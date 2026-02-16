"""Price alert service for user subscriptions."""

import uuid
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.price_alert import PriceAlert
from app.models.product import Product


class AlertService:
    """Handles CRUD for user price alerts."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_alerts_for_user(
        self, user_id: uuid.UUID, active_only: bool = True
    ) -> List[PriceAlert]:
        """Get all price alerts for a user."""
        stmt = (
            select(PriceAlert)
            .options(selectinload(PriceAlert.product))
            .where(PriceAlert.user_id == user_id)
        )
        if active_only:
            stmt = stmt.where(PriceAlert.is_active == True)
        stmt = stmt.order_by(PriceAlert.created_at.desc())

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_alert(
        self,
        user_id: uuid.UUID,
        product_id: uuid.UUID,
        target_price: Decimal,
    ) -> PriceAlert:
        """Create a new price alert. Returns existing alert if duplicate."""
        # Check for existing active alert
        stmt = select(PriceAlert).where(
            PriceAlert.user_id == user_id,
            PriceAlert.product_id == product_id,
            PriceAlert.is_active == True,
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Update target price
            existing.target_price = target_price
            await self.db.flush()
            return existing

        alert = PriceAlert(
            user_id=user_id,
            product_id=product_id,
            target_price=target_price,
        )
        self.db.add(alert)
        await self.db.flush()
        return alert

    async def delete_alert(
        self, alert_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        """Deactivate a price alert."""
        stmt = select(PriceAlert).where(
            PriceAlert.id == alert_id,
            PriceAlert.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        alert = result.scalar_one_or_none()

        if not alert:
            return False

        alert.is_active = False
        return True
