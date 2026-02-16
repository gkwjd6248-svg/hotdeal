"""Comments API endpoints (nested under /deals/{deal_id}/comments)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.comment import CommentCreateRequest, CommentResponse, CommentUpdateRequest
from app.schemas.common import ApiResponse
from app.services.comment_service import CommentService

router = APIRouter()


@router.get("/{deal_id}/comments", response_model=ApiResponse)
async def list_comments(deal_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get all comments for a deal (with nested replies)."""
    service = CommentService(db)
    comments = await service.get_comments_for_deal(deal_id)

    return ApiResponse(
        status="success",
        data=[CommentResponse.model_validate(c).model_dump(mode="json") for c in comments],
    )


@router.post("/{deal_id}/comments", response_model=ApiResponse, status_code=201)
async def create_comment(
    deal_id: UUID,
    body: CommentCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new comment on a deal. Requires authentication."""
    service = CommentService(db)
    comment = await service.create_comment(
        deal_id=deal_id,
        user_id=current_user.id,
        content=body.content,
        parent_id=body.parent_id,
    )

    if not comment:
        raise HTTPException(status_code=404, detail="딜 또는 상위 댓글을 찾을 수 없습니다")

    return ApiResponse(
        status="success",
        data=CommentResponse.model_validate(comment).model_dump(mode="json"),
    )


@router.put("/{deal_id}/comments/{comment_id}", response_model=ApiResponse)
async def update_comment(
    deal_id: UUID,
    comment_id: UUID,
    body: CommentUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a comment. Only the author can edit."""
    service = CommentService(db)
    comment = await service.update_comment(
        comment_id=comment_id,
        user_id=current_user.id,
        content=body.content,
    )

    if not comment:
        raise HTTPException(status_code=404, detail="댓글을 찾을 수 없습니다")

    return ApiResponse(
        status="success",
        data=CommentResponse.model_validate(comment).model_dump(mode="json"),
    )


@router.delete("/{deal_id}/comments/{comment_id}", response_model=ApiResponse)
async def delete_comment(
    deal_id: UUID,
    comment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a comment (soft delete). Only the author can delete."""
    service = CommentService(db)
    success = await service.delete_comment(
        comment_id=comment_id,
        user_id=current_user.id,
    )

    if not success:
        raise HTTPException(status_code=404, detail="댓글을 찾을 수 없습니다")

    return ApiResponse(status="success", data={"deleted": True})
