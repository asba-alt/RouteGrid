from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DriverCreate(BaseModel):
    name: Optional[str] = None


class DriverRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: Optional[str] = None


class VehicleCreate(BaseModel):
    external_id: Optional[str] = None
    driver_id: Optional[UUID] = None
    depot_warehouse_id: Optional[UUID] = None
    max_weight_kg: Decimal
    operational: bool = True


class VehicleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    external_id: Optional[str] = None
    driver_id: Optional[UUID] = None
    depot_warehouse_id: Optional[UUID] = None
    max_weight_kg: Decimal
    operational: bool


class VehicleUpdate(BaseModel):
    external_id: Optional[str] = None
    driver_id: Optional[UUID] = None
    depot_warehouse_id: Optional[UUID] = None
    operational: Optional[bool] = None


class VehicleDetail(VehicleRead):
    driver: Optional[DriverRead] = None
