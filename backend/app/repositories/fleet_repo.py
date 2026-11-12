from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import Driver, Route, Vehicle, Warehouse
from app.repositories.route_repo import ACTIVE_ROUTE_STATUSES


class DriverRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, name: Optional[str]) -> Driver:
        driver = Driver(name=name)
        self.session.add(driver)
        await self.session.flush()
        return driver

    async def get_all(self) -> list[Driver]:
        stmt = select(Driver).order_by(Driver.name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, id: UUID) -> Optional[Driver]:
        result = await self.session.execute(select(Driver).where(Driver.id == id))
        return result.scalar_one_or_none()


class VehicleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        external_id: Optional[str],
        driver_id: Optional[UUID],
        depot_warehouse_id: Optional[UUID],
        max_weight_kg: Decimal,
        operational: bool,
    ) -> Vehicle:
        vehicle = Vehicle(
            external_id=external_id,
            driver_id=driver_id,
            depot_warehouse_id=depot_warehouse_id,
            max_weight_kg=max_weight_kg,
            operational=operational,
        )
        self.session.add(vehicle)
        await self.session.flush()
        return vehicle

    async def get_all(self, operational: Optional[bool] = None) -> list[Vehicle]:
        stmt = select(Vehicle).order_by(Vehicle.external_id)
        if operational is not None:
            stmt = stmt.where(Vehicle.operational == operational)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, id: UUID) -> Optional[Vehicle]:
        stmt = (
            select(Vehicle)
            .where(Vehicle.id == id)
            .options(joinedload(Vehicle.driver))
        )
        result = await self.session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def update(self, vehicle: Vehicle, **kwargs) -> Vehicle:
        for key, value in kwargs.items():
            setattr(vehicle, key, value)
        await self.session.flush()
        return vehicle

    async def get_routable_with_depot(self) -> list[tuple[Vehicle, Warehouse]]:
        """Operational vehicles joined to their depot warehouse (FR-22).

        Vehicles without a depot, or whose depot is missing, cannot be routed
        and are therefore excluded here rather than filtered later. Vehicles
        already holding an active route are excluded too, so a batch solve
        cannot double-book one (FR-28: one route per vehicle per cycle).
        """
        busy_vehicle_ids = select(Route.vehicle_id).where(
            Route.status.in_(ACTIVE_ROUTE_STATUSES),
            Route.vehicle_id.is_not(None),
        )
        stmt = (
            select(Vehicle, Warehouse)
            .join(Warehouse, Vehicle.depot_warehouse_id == Warehouse.id)
            .where(
                Vehicle.operational.is_(True),
                Vehicle.id.not_in(busy_vehicle_ids),
            )
            .order_by(Vehicle.external_id)
        )
        result = await self.session.execute(stmt)
        return [(vehicle, depot) for vehicle, depot in result.all()]

    async def count(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(Vehicle))
        return result.scalar_one()
