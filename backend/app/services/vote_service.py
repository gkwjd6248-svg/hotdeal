"""Vote service for tracking per-user deal votes."""

import uuid
from typing import Optional, Dict, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deal import Deal
from app.models.user_vote import UserVote


class VoteService:
    """Handles deal voting with per-user tracking."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def vote(
        self,
        deal_id: uuid.UUID,
        user_id: uuid.UUID,
        vote_type: str,
    ) -> Optional[Dict[str, Any]]:
        """Cast or change a vote on a deal.

        If user already voted the same way, removes the vote (toggle).
        If user voted differently, switches the vote.

        Returns dict with vote_up, vote_down, user_vote, or None if deal not found.
        """
        # Get deal first (ensures it exists)
        deal_stmt = select(Deal).where(Deal.id == deal_id)
        deal_result = await self.db.execute(deal_stmt)
        deal = deal_result.scalar_one_or_none()

        if not deal:
            return None

        # Get existing vote
        stmt = select(UserVote).where(
            UserVote.user_id == user_id,
            UserVote.deal_id == deal_id,
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        user_vote = None

        if existing:
            if existing.vote_type == vote_type:
                # Toggle off: remove vote
                if vote_type == "up":
                    deal.vote_up = max(0, deal.vote_up - 1)
                else:
                    deal.vote_down = max(0, deal.vote_down - 1)
                await self.db.delete(existing)
                user_vote = None
            else:
                # Switch vote
                if existing.vote_type == "up":
                    deal.vote_up = max(0, deal.vote_up - 1)
                    deal.vote_down += 1
                else:
                    deal.vote_down = max(0, deal.vote_down - 1)
                    deal.vote_up += 1
                existing.vote_type = vote_type
                user_vote = vote_type
        else:
            # New vote
            new_vote = UserVote(
                user_id=user_id,
                deal_id=deal_id,
                vote_type=vote_type,
            )
            self.db.add(new_vote)
            if vote_type == "up":
                deal.vote_up += 1
            else:
                deal.vote_down += 1
            user_vote = vote_type

        await self.db.flush()

        return {
            "deal_id": str(deal.id),
            "vote_up": deal.vote_up,
            "vote_down": deal.vote_down,
            "user_vote": user_vote,
        }

    async def get_user_vote(
        self,
        deal_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Optional[str]:
        """Get the current user's vote type for a deal, or None."""
        stmt = select(UserVote.vote_type).where(
            UserVote.user_id == user_id,
            UserVote.deal_id == deal_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
