from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import GeoPoint


class OrderItemCreate(BaseModel):
    sku: str
    quantity: int = Field(gt=0)
    weight_kg: Decimal = Field(ge=0)


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    sku: str
    quantity: int
    weight_kg: Decimal


class OrderCreate(BaseModel):
    customer_id: Optional[UUID] = None
    customer_name: Optional[str] = None
    delivery_location: Optional[GeoPoint] = None
    items: list[OrderItemCreate] = Field(min_length=1)


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: Optional[UUID] = None
    customer_name: Optional[str] = None
    reference: Optional[str] = None
    status: str
    created_at: datetime


class ReservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    warehouse_id: UUID
    order_id: UUID
    sku: str
    quantity: int
    expires_at: Optional[datetime] = None


class OrderDetail(OrderRead):
    items: list[OrderItemRead] = []
    delivery_location: Optional[GeoPoint] = None
    reservations: list[ReservationRead] = []


class OrderStatusUpdate(BaseModel):
    status: str


class OrderIntakeRequest(BaseModel):
    """Order intake payload (Phase 3). A warehouse must be supplied because
    warehouse selection (FR-15/FR-16) is a separate component."""

    customer_id: Optional[UUID] = None
    customer_name: Optional[str] = None
    warehouse_id: UUID
    delivery_location: Optional[GeoPoint] = None
    items: list[OrderItemCreate] = Field(min_length=1)


class OrderIntakeResponse(OrderDetail):
    warehouse_id: UUID
