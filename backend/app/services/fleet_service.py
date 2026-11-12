from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Driver, Vehicle
from app.repositories.fleet_repo import DriverRepository, VehicleRepository
from app.repositories.warehouse_repo import WarehouseRepository
from app.schemas.fleet import (
    DriverCreate,
    DriverRead,
    VehicleCreate,
    VehicleDetail,
    VehicleRead,
    VehicleUpdate,
)


async def create_driver(session: AsyncSession, data: DriverCreate) -> DriverRead:
    repo = DriverRepository(session)
    driver = await repo.create(name=data.name)
    await session.commit()
    return DriverRead.model_validate(driver)


async def list_drivers(session: AsyncSession) -> list[DriverRead]:
    repo = DriverRepository(session)
    drivers = await repo.get_all()
    return [DriverRead.model_validate(d) for d in drivers]


async def _validate_refs(
    session: AsyncSession,
    driver_id: Optional[UUID],
    depot_warehouse_id: Optional[UUID],
) -> None:
    if driver_id is not None:
        if await DriverRepository(session).get_by_id(driver_id) is None:
            raise HTTPException(status_code=404, detail="Driver not found")
    if depot_warehouse_id is not None:
        if await WarehouseRepository(session).get_by_id(depot_warehouse_id) is None:
            raise HTTPException(status_code=404, detail="Warehouse not found")


async def create_vehicle(session: AsyncSession, data: VehicleCreate) -> VehicleRead:
    await _validate_refs(session, data.driver_id, data.depot_warehouse_id)
    repo = VehicleRepository(session)
    vehicle = await repo.create(
        external_id=data.external_id,
        driver_id=data.driver_id,
        depot_warehouse_id=data.depot_warehouse_id,
        max_weight_kg=data.max_weight_kg,
        operational=data.operational,
    )
    await session.commit()
    return VehicleRead.model_validate(vehicle)


async def list_vehicles(
    session: AsyncSession, operational: Optional[bool] = None
) -> list[VehicleRead]:
    repo = VehicleRepository(session)
    vehicles = await repo.get_all(operational=operational)
    return [VehicleRead.model_validate(v) for v in vehicles]


async def get_vehicle(session: AsyncSession, id: UUID) -> VehicleDetail:
    repo = VehicleRepository(session)
    vehicle = await repo.get_by_id(id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return VehicleDetail(
        id=vehicle.id,
        external_id=vehicle.external_id,
        driver_id=vehicle.driver_id,
        depot_warehouse_id=vehicle.depot_warehouse_id,
        max_weight_kg=vehicle.max_weight_kg,
        operational=vehicle.operational,
        driver=DriverRead.model_validate(vehicle.driver) if vehicle.driver else None,
    )


async def update_vehicle(
    session: AsyncSession, id: UUID, data: VehicleUpdate
) -> VehicleRead:
    repo = VehicleRepository(session)
    vehicle: Optional[Vehicle] = await repo.get_by_id(id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    changes = data.model_dump(exclude_unset=True)
    if "driver_id" in changes or "depot_warehouse_id" in changes:
        await _validate_refs(
            session,
            changes.get("driver_id"),
            changes.get("depot_warehouse_id"),
        )
    await repo.update(vehicle, **changes)
    await session.commit()
    return VehicleRead.model_validate(vehicle)
