"""Pydantic schemas for DealHawk API.

All request/response models are defined here for easy import.
"""

from app.schemas.common import ApiResponse, ErrorDetail, ErrorResponse, PaginationMeta
from app.schemas.deal import CategoryBrief, DealDetailResponse, DealResponse, ShopBrief, VoteRequest
from app.schemas.category import CategoryResponse, CategoryTreeResponse
from app.schemas.shop import ShopResponse
from app.schemas.product import PriceHistoryPoint, ProductDetailResponse, ProductResponse
from app.schemas.search import RecentKeywordResponse, TrendingKeywordResponse
from app.schemas.health import HealthCheckResponse
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserBrief,
    UserResponse,
)
from app.schemas.comment import CommentCreateRequest, CommentResponse, CommentUpdateRequest
from app.schemas.alert import AlertCreateRequest, AlertResponse

__all__ = [
    # Common
    "ApiResponse",
    "ErrorDetail",
    "ErrorResponse",
    "PaginationMeta",
    # Deal
    "DealResponse",
    "DealDetailResponse",
    "ShopBrief",
    "CategoryBrief",
    "VoteRequest",
    # Category
    "CategoryResponse",
    "CategoryTreeResponse",
    # Shop
    "ShopResponse",
    # Product
    "ProductResponse",
    "ProductDetailResponse",
    "PriceHistoryPoint",
    # Search
    "TrendingKeywordResponse",
    "RecentKeywordResponse",
    # Health
    "HealthCheckResponse",
    # Auth
    "LoginRequest",
    "RegisterRequest",
    "TokenResponse",
    "UserBrief",
    "UserResponse",
    # Comment
    "CommentCreateRequest",
    "CommentResponse",
    "CommentUpdateRequest",
    # Alert
    "AlertCreateRequest",
    "AlertResponse",
]
