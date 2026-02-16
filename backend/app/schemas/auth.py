"""Auth Pydantic schemas for request/response validation."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator


class RegisterRequest(BaseModel):
    """User registration request."""
    email: EmailStr
    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isalpha() for c in v):
            raise ValueError("비밀번호에 영문자가 포함되어야 합니다")
        if not any(c.isdigit() for c in v):
            raise ValueError("비밀번호에 숫자가 포함되어야 합니다")
        return v


class LoginRequest(BaseModel):
    """User login request."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Public user info response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    username: str
    is_active: bool
    created_at: datetime


class UserBrief(BaseModel):
    """Minimal user info for embedding in other responses."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
