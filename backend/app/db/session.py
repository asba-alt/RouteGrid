from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

async_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def init_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    global async_session_factory
    async_session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if async_session_factory is None:
        raise RuntimeError("Session factory is not initialized")
    async with async_session_factory() as session:
        yield session
