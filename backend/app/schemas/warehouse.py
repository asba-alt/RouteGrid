from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import GeoPoint


class InventoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    warehouse_id: UUID
    sku: str
    on_hand: int
    reserved: int


class InventoryUpsert(BaseModel):
    on_hand: int = Field(ge=0)
    # None means "leave the existing hold count alone". It must NOT default to 0:
    # doing so silently wiped active reservations when an operator only wanted to
    # correct the on-hand quantity.
    reserved: Optional[int] = Field(default=None, ge=0)


class WarehouseCreate(BaseModel):
    name: str
    location: GeoPoint
    operational: bool = True


class WarehouseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    location: GeoPoint
    operational: bool


class WarehouseUpdate(BaseModel):
    name: Optional[str] = None
    operational: Optional[bool] = None


class WarehouseDetail(WarehouseRead):
    inventory: list[InventoryRead] = []
