"""Search Pydantic schemas for request/response validation."""

from pydantic import BaseModel


class TrendingKeywordResponse(BaseModel):
    """Trending keyword response schema."""

    keyword: str
    count: int


class RecentKeywordResponse(BaseModel):
    """Recently searched keyword response schema."""

    keyword: str
    last_searched_at: str
    count: int
