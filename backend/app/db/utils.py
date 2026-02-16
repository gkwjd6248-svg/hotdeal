"""Database utility functions and common queries."""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions.

    Usage in FastAPI endpoints:
        @router.get("/products")
        async def list_products(db: AsyncSession = Depends(get_db)):
            ...

    The session is automatically closed after the request completes.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_health() -> dict[str, bool]:
    """Check if database is accessible and responsive.

    Returns:
        dict with 'healthy' boolean and optional 'error' message
    """
    try:
        async with async_session_factory() as session:
            await session.execute("SELECT 1")
            return {"healthy": True}
    except Exception as e:
        return {"healthy": False, "error": str(e)}
