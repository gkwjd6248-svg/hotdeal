"""Authentication service: JWT tokens, password hashing, user management."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: uuid.UUID) -> str:
    """Create a JWT access token for the given user ID."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    """Decode a JWT token and return the user ID string, or None if invalid."""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload.get("sub")
    except JWTError:
        return None


class AuthService:
    """Handles user registration, login, and lookup."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(
        self, email: str, username: str, password: str
    ) -> User:
        """Register a new user. Raises ValueError if email/username taken."""
        # Check existing email
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            raise ValueError("이미 사용 중인 이메일입니다")

        # Check existing username
        stmt = select(User).where(User.username == username)
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            raise ValueError("이미 사용 중인 닉네임입니다")

        user = User(
            email=email,
            username=username,
            hashed_password=hash_password(password),
        )
        self.db.add(user)
        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            raise ValueError("이미 사용 중인 이메일 또는 닉네임입니다")
        return user

    async def authenticate(self, email: str, password: str) -> Optional[User]:
        """Verify credentials and return user, or None if invalid."""
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.hashed_password):
            return None

        if not user.is_active:
            return None

        # Update last login
        user.last_login_at = datetime.now(timezone.utc)
        return user

    async def get_user_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        """Fetch user by ID."""
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
