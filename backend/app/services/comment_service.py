"""Comment service for deal discussions."""

import uuid
from typing import List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.comment import Comment
from app.models.deal import Deal


class CommentService:
    """Handles CRUD operations for deal comments."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_comments_for_deal(
        self, deal_id: uuid.UUID
    ) -> List[Comment]:
        """Get all top-level comments for a deal with nested replies."""
        stmt = (
            select(Comment)
            .where(Comment.deal_id == deal_id, Comment.parent_id.is_(None), Comment.is_deleted == False)
            .options(
                selectinload(Comment.user),
                selectinload(Comment.replies).selectinload(Comment.user),
            )
            .order_by(Comment.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_comment(
        self,
        deal_id: uuid.UUID,
        user_id: uuid.UUID,
        content: str,
        parent_id: Optional[uuid.UUID] = None,
    ) -> Optional[Comment]:
        """Create a new comment on a deal. Returns None if deal not found."""
        # Validate deal exists
        deal_check = await self.db.execute(select(Deal).where(Deal.id == deal_id))
        if not deal_check.scalar_one_or_none():
            return None

        # Validate parent comment if replying
        if parent_id:
            parent_check = await self.db.execute(
                select(Comment).where(
                    Comment.id == parent_id,
                    Comment.deal_id == deal_id,
                    Comment.is_deleted == False,
                )
            )
            if not parent_check.scalar_one_or_none():
                return None

        comment = Comment(
            deal_id=deal_id,
            user_id=user_id,
            content=content,
            parent_id=parent_id,
        )
        self.db.add(comment)
        await self.db.flush()

        # Increment deal comment_count
        stmt = select(Deal).where(Deal.id == deal_id)
        result = await self.db.execute(stmt)
        deal = result.scalar_one_or_none()
        if deal:
            deal.comment_count = deal.comment_count + 1

        # Reload with user relationship
        await self.db.refresh(comment, ["user"])
        return comment

    async def update_comment(
        self,
        comment_id: uuid.UUID,
        user_id: uuid.UUID,
        content: str,
    ) -> Optional[Comment]:
        """Update a comment's content. Only the author can edit."""
        stmt = select(Comment).where(
            Comment.id == comment_id,
            Comment.user_id == user_id,
            Comment.is_deleted == False,
        )
        result = await self.db.execute(stmt)
        comment = result.scalar_one_or_none()

        if not comment:
            return None

        comment.content = content
        await self.db.flush()
        await self.db.refresh(comment, ["user"])
        return comment

    async def delete_comment(
        self,
        comment_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Soft-delete a comment. Only the author can delete."""
        stmt = select(Comment).where(
            Comment.id == comment_id,
            Comment.user_id == user_id,
            Comment.is_deleted == False,
        )
        result = await self.db.execute(stmt)
        comment = result.scalar_one_or_none()

        if not comment:
            return False

        comment.is_deleted = True
        comment.content = "삭제된 댓글입니다"

        # Decrement deal comment_count
        deal_stmt = select(Deal).where(Deal.id == comment.deal_id)
        deal_result = await self.db.execute(deal_stmt)
        deal = deal_result.scalar_one_or_none()
        if deal and deal.comment_count > 0:
            deal.comment_count = deal.comment_count - 1

        return True
