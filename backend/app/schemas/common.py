"""Common Pydantic schemas used across the API."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginationMeta(BaseModel):
    """Pagination metadata included in list responses."""

    page: int = 1
    limit: int = 20  # Changed from 'size' to 'limit' for consistency
    total: int = 0
    total_pages: int = 0


class ApiResponse(BaseModel, Generic[T]):
    """Standard API response envelope."""

    status: str = "success"
    data: T
    meta: PaginationMeta | None = None


class ErrorDetail(BaseModel):
    """Error detail for error responses."""

    code: str
    message: str
    field: str | None = None


class ErrorResponse(BaseModel):
    """Standard API error response."""

    status: str = "error"
    error: ErrorDetail
