from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.db.session import get_db
from app.schemas.warehouse import (
    InventoryRead,
    InventoryUpsert,
    WarehouseCreate,
    WarehouseDetail,
    WarehouseRead,
    WarehouseUpdate,
)
from app.services import warehouse_service

router = APIRouter(prefix="/api/v1/warehouses", tags=["warehouses"])


@router.post("", response_model=WarehouseRead, status_code=status.HTTP_201_CREATED)
async def create_warehouse(
    payload: WarehouseCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> WarehouseRead:
    return await warehouse_service.create_warehouse(db, payload)


@router.get("", response_model=list[WarehouseRead])
async def list_warehouses(
    operational: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[WarehouseRead]:
    return await warehouse_service.list_warehouses(db, operational)


@router.get("/{warehouse_id}", response_model=WarehouseDetail)
async def get_warehouse(
    warehouse_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> WarehouseDetail:
    return await warehouse_service.get_warehouse(db, warehouse_id)


@router.patch("/{warehouse_id}", response_model=WarehouseRead)
async def update_warehouse(
    warehouse_id: UUID,
    payload: WarehouseUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> WarehouseRead:
    return await warehouse_service.update_warehouse(db, warehouse_id, payload)


@router.get("/{warehouse_id}/inventory", response_model=list[InventoryRead])
async def get_inventory(
    warehouse_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[InventoryRead]:
    return await warehouse_service.get_inventory(db, warehouse_id)


@router.put("/{warehouse_id}/inventory/{sku}", response_model=InventoryRead)
async def upsert_inventory(
    warehouse_id: UUID,
    sku: str,
    payload: InventoryUpsert,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> InventoryRead:
    return await warehouse_service.upsert_inventory(db, warehouse_id, sku, payload)
