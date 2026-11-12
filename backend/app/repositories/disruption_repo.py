from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Disruption, Route


class DisruptionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **values) -> Disruption:
        disruption = Disruption(**values)
        self.session.add(disruption)
        await self.session.flush()
        return disruption

    async def get_by_id(self, disruption_id: UUID) -> Optional[Disruption]:
        result = await self.session.execute(
            select(Disruption).where(Disruption.id == disruption_id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self, status: Optional[str] = None, limit: int = 50, offset: int = 0
    ) -> list[Disruption]:
        stmt = select(Disruption).order_by(Disruption.created_at.desc())
        if status is not None:
            stmt = stmt.where(Disruption.status == status)
        result = await self.session.execute(stmt.limit(limit).offset(offset))
        return list(result.scalars().all())

    async def count(self, status: Optional[str] = None) -> int:
        stmt = select(func.count()).select_from(Disruption)
        if status is not None:
            stmt = stmt.where(Disruption.status == status)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_route_with_stops(self, route_id: UUID) -> Optional[Route]:
        result = await self.session.execute(
            select(Route)
            .where(Route.id == route_id)
            .options(selectinload(Route.stops))
        )
        return result.scalar_one_or_none()
