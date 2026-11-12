"""Route lookups for the simulator (Phase 5).

Route lifecycle vocabulary used by v1: PLANNED -> IN_PROGRESS -> COMPLETED.
Route stops move PENDING -> COMPLETED (service time is not modelled, so
arriving at a stop completes it).
"""
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Route, Vehicle, Warehouse

ROUTE_PLANNED = "PLANNED"
ROUTE_IN_PROGRESS = "IN_PROGRESS"
ROUTE_COMPLETED = "COMPLETED"
ROUTE_CANCELLED = "CANCELLED"

ROUTE_STOP_PENDING = "PENDING"
ROUTE_STOP_COMPLETED = "COMPLETED"
ROUTE_STOP_RELEASED = "RELEASED"

ACTIVE_ROUTE_STATUSES = (ROUTE_PLANNED, ROUTE_IN_PROGRESS)


class RouteRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active_with_stops(self) -> list[Route]:
        stmt = (
            select(Route)
            .where(Route.status.in_(ACTIVE_ROUTE_STATUSES))
            .options(selectinload(Route.stops))
            .order_by(Route.created_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id_with_stops(self, route_id: UUID) -> Optional[Route]:
        stmt = (
            select(Route)
            .where(Route.id == route_id)
            .options(selectinload(Route.stops))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_with_stops(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Route]:
        stmt = (
            select(Route)
            .options(selectinload(Route.stops))
            .order_by(Route.created_at.desc())
        )
        if status is not None:
            stmt = stmt.where(Route.status == status)
        result = await self.session.execute(stmt.limit(limit).offset(offset))
        return list(result.scalars().all())

    async def count(self, status: Optional[str] = None) -> int:
        stmt = select(func.count()).select_from(Route)
        if status is not None:
            stmt = stmt.where(Route.status == status)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_depot_for_route(self, route: Route) -> Optional[Warehouse]:
        """The depot the vehicle starts and ends at, if it has one."""
        if route.vehicle_id is None:
            return None
        stmt = (
            select(Warehouse)
            .join(Vehicle, Vehicle.depot_warehouse_id == Warehouse.id)
            .where(Vehicle.id == route.vehicle_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
