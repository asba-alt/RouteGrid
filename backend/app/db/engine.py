from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def create_engine_from_url(url: str, echo: bool = False) -> AsyncEngine:
    return create_async_engine(
        url,
        echo=echo,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
