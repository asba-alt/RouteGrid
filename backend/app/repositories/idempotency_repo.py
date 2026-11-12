from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IdempotencyKey


class IdempotencyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_order_id(self, key: str) -> Optional[UUID]:
        result = await self.session.execute(
            select(IdempotencyKey.order_id).where(IdempotencyKey.key == key)
        )
        return result.scalar_one_or_none()

    async def remember(self, key: str, order_id: UUID) -> None:
        self.session.add(IdempotencyKey(key=key, order_id=order_id))
        await self.session.flush()
