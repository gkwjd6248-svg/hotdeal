"""Price alert API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.alert import AlertCreateRequest, AlertResponse
from app.schemas.common import ApiResponse
from app.services.alert_service import AlertService

router = APIRouter()


@router.get("", response_model=ApiResponse)
async def list_alerts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all active price alerts for the current user."""
    service = AlertService(db)
    alerts = await service.get_alerts_for_user(current_user.id)

    return ApiResponse(
        status="success",
        data=[AlertResponse.model_validate(a).model_dump(mode="json") for a in alerts],
    )


@router.post("", response_model=ApiResponse, status_code=201)
async def create_alert(
    body: AlertCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or update a price alert for a product."""
    service = AlertService(db)
    alert = await service.create_alert(
        user_id=current_user.id,
        product_id=body.product_id,
        target_price=body.target_price,
    )

    return ApiResponse(
        status="success",
        data=AlertResponse.model_validate(alert).model_dump(mode="json"),
    )


@router.delete("/{alert_id}", response_model=ApiResponse)
async def delete_alert(
    alert_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate a price alert."""
    service = AlertService(db)
    success = await service.delete_alert(alert_id, current_user.id)

    if not success:
        raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다")

    return ApiResponse(status="success", data={"deleted": True})
