from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Inventory, Warehouse
from app.repositories.warehouse_repo import WarehouseRepository
from app.schemas.common import GeoPoint, wkb_to_geo_point
from app.schemas.warehouse import (
    InventoryRead,
    InventoryUpsert,
    WarehouseCreate,
    WarehouseDetail,
    WarehouseRead,
    WarehouseUpdate,
)


def geo_point_to_wkt(point: GeoPoint) -> str:
    return f"SRID=4326;POINT({point.lng} {point.lat})"


def warehouse_to_read(warehouse: Warehouse) -> WarehouseRead:
    return WarehouseRead(
        id=warehouse.id,
        name=warehouse.name,
        location=wkb_to_geo_point(warehouse.location),
        operational=warehouse.operational,
    )


async def create_warehouse(
    session: AsyncSession, data: WarehouseCreate
) -> WarehouseRead:
    repo = WarehouseRepository(session)
    warehouse = await repo.create(
        name=data.name,
        location_wkt=geo_point_to_wkt(data.location),
        operational=data.operational,
    )
    await session.commit()
    return WarehouseRead(
        id=warehouse.id,
        name=warehouse.name,
        location=data.location,
        operational=warehouse.operational,
    )


async def list_warehouses(
    session: AsyncSession, operational: Optional[bool] = None
) -> list[WarehouseRead]:
    repo = WarehouseRepository(session)
    warehouses = await repo.get_all(operational=operational)
    return [warehouse_to_read(w) for w in warehouses]


async def get_warehouse(session: AsyncSession, id: UUID) -> WarehouseDetail:
    repo = WarehouseRepository(session)
    warehouse = await repo.get_by_id(id)
    if warehouse is None:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return WarehouseDetail(
        id=warehouse.id,
        name=warehouse.name,
        location=wkb_to_geo_point(warehouse.location),
        operational=warehouse.operational,
        inventory=[InventoryRead.model_validate(i) for i in warehouse.inventory],
    )


async def update_warehouse(
    session: AsyncSession, id: UUID, data: WarehouseUpdate
) -> WarehouseRead:
    repo = WarehouseRepository(session)
    warehouse = await repo.get_by_id(id)
    if warehouse is None:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    await repo.update(warehouse, **data.model_dump(exclude_unset=True))
    await session.commit()
    return warehouse_to_read(warehouse)


async def get_inventory(
    session: AsyncSession, warehouse_id: UUID
) -> list[InventoryRead]:
    repo = WarehouseRepository(session)
    if await repo.get_by_id(warehouse_id) is None:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    inventory = await repo.get_inventory(warehouse_id)
    return [InventoryRead.model_validate(i) for i in inventory]


async def upsert_inventory(
    session: AsyncSession,
    warehouse_id: UUID,
    sku: str,
    data: InventoryUpsert,
) -> InventoryRead:
    repo = WarehouseRepository(session)
    if await repo.get_by_id(warehouse_id) is None:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    inventory: Inventory = await repo.upsert_inventory(
        warehouse_id=warehouse_id,
        sku=sku,
        on_hand=data.on_hand,
        reserved=data.reserved,
    )
    await session.commit()
    return InventoryRead.model_validate(inventory)
