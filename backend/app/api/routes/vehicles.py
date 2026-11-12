from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.db.session import get_db
from app.schemas.fleet import (
    DriverCreate,
    DriverRead,
    VehicleCreate,
    VehicleDetail,
    VehicleRead,
    VehicleUpdate,
)
from app.services import fleet_service

router = APIRouter(prefix="/api/v1", tags=["fleet"])


@router.post("/drivers", response_model=DriverRead, status_code=status.HTTP_201_CREATED)
async def create_driver(
    payload: DriverCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> DriverRead:
    return await fleet_service.create_driver(db, payload)


@router.get("/drivers", response_model=list[DriverRead])
async def list_drivers(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[DriverRead]:
    return await fleet_service.list_drivers(db)


@router.post("/vehicles", response_model=VehicleRead, status_code=status.HTTP_201_CREATED)
async def create_vehicle(
    payload: VehicleCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> VehicleRead:
    return await fleet_service.create_vehicle(db, payload)


@router.get("/vehicles", response_model=list[VehicleRead])
async def list_vehicles(
    operational: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[VehicleRead]:
    return await fleet_service.list_vehicles(db, operational)


@router.get("/vehicles/{vehicle_id}", response_model=VehicleDetail)
async def get_vehicle(
    vehicle_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> VehicleDetail:
    return await fleet_service.get_vehicle(db, vehicle_id)


@router.patch("/vehicles/{vehicle_id}", response_model=VehicleRead)
async def update_vehicle(
    vehicle_id: UUID,
    payload: VehicleUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> VehicleRead:
    return await fleet_service.update_vehicle(db, vehicle_id, payload)
