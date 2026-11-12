from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> JSONResponse:
    database_status = "connected"
    redis_status = "connected"

    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        database_status = "error"

    try:
        await redis.ping()
    except Exception:
        redis_status = "error"

    if database_status == "connected" and redis_status == "connected":
        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "database": database_status,
                "redis": redis_status,
            },
        )

    return JSONResponse(
        status_code=503,
        content={
            "status": "error",
            "database": database_status,
            "redis": redis_status,
        },
    )
