from typing import Optional

from redis.asyncio import Redis

redis_client: Optional[Redis] = None


async def get_redis_client(url: str) -> Redis:
    # RESP2 keeps compatibility across Redis 5.x up to managed 7.x providers;
    # redis-py defaults to RESP3 (HELLO 3), which older servers reject.
    return Redis.from_url(
        url, encoding="utf-8", decode_responses=True, protocol=2
    )


async def init_redis(url: str) -> Redis:
    global redis_client
    redis_client = await get_redis_client(url)
    return redis_client


async def close_redis() -> None:
    global redis_client
    if redis_client is not None:
        await redis_client.aclose()
        redis_client = None


async def get_redis() -> Redis:
    if redis_client is None:
        raise RuntimeError("Redis client is not initialized")
    return redis_client
