"""Authentication API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.schemas.common import ApiResponse
from app.services.auth_service import AuthService, create_access_token

router = APIRouter()


@router.post("/register", response_model=ApiResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user account."""
    service = AuthService(db)
    try:
        user = await service.register(
            email=body.email,
            username=body.username,
            password=body.password,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    token = create_access_token(user.id)
    return ApiResponse(
        status="success",
        data={
            "user": UserResponse.model_validate(user).model_dump(mode="json"),
            "token": TokenResponse(access_token=token).model_dump(),
        },
    )


@router.post("/login", response_model=ApiResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with email and password."""
    service = AuthService(db)
    user = await service.authenticate(email=body.email, password=body.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다",
        )

    token = create_access_token(user.id)
    return ApiResponse(
        status="success",
        data={
            "user": UserResponse.model_validate(user).model_dump(mode="json"),
            "token": TokenResponse(access_token=token).model_dump(),
        },
    )


@router.get("/me", response_model=ApiResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user info."""
    return ApiResponse(
        status="success",
        data=UserResponse.model_validate(current_user).model_dump(mode="json"),
    )
