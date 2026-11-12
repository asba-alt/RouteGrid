from typing import Optional
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order
from app.repositories.order_repo import OrderRepository
from app.repositories.reservation_repo import ReservationRepository
from app.schemas.common import wkb_to_geo_point
from app.schemas.order import (
    OrderCreate,
    OrderDetail,
    OrderItemRead,
    OrderRead,
    OrderStatusUpdate,
    ReservationRead,
)
from app.services.warehouse_service import geo_point_to_wkt

PENDING_ALLOCATION = "PENDING_ALLOCATION"

# Order lifecycle per requirements.md FR-6. Terminal states are DELIVERED,
# CANCELLED and FAILED. FR-4: cancellation is rejected once a group has reached
# OUT_FOR_DELIVERY or later, so OUT_FOR_DELIVERY cannot transition to CANCELLED.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    PENDING_ALLOCATION: {"ALLOCATED", "CANCELLED", "FAILED"},
    "ALLOCATED": {"PICKING", "CANCELLED", "FAILED"},
    "PICKING": {"READY_FOR_DISPATCH", "CANCELLED", "FAILED"},
    "READY_FOR_DISPATCH": {"OUT_FOR_DELIVERY", "CANCELLED", "FAILED"},
    "OUT_FOR_DELIVERY": {"DELIVERED", "PARTIALLY_SHIPPED", "FAILED"},
    "PARTIALLY_SHIPPED": {"DELIVERED", "FAILED"},
    "DELIVERED": set(),
    "CANCELLED": set(),
    "FAILED": set(),
}


def new_reference() -> str:
    """Short, human-readable order reference for operator workflows."""
    return f"ORD-{uuid4().hex[:8].upper()}"


def order_to_detail(order: Order) -> OrderDetail:
    return OrderDetail(
        id=order.id,
        customer_id=order.customer_id,
        customer_name=order.customer_name,
        reference=order.reference,
        status=order.status,
        created_at=order.created_at,
        items=[OrderItemRead.model_validate(i) for i in order.items],
        delivery_location=(
            wkb_to_geo_point(order.delivery_location)
            if order.delivery_location is not None
            else None
        ),
    )


async def _with_reservations(
    session: AsyncSession, detail: OrderDetail, order_id
) -> OrderDetail:
    """Attach the order's inventory holds so the UI can show what is reserved."""
    rows = await ReservationRepository(session).list_for_order(order_id)
    detail.reservations = [ReservationRead.model_validate(row) for row in rows]
    return detail


async def create_order(session: AsyncSession, data: OrderCreate) -> OrderDetail:
    repo = OrderRepository(session)
    wkt = (
        geo_point_to_wkt(data.delivery_location)
        if data.delivery_location is not None
        else None
    )
    order = await repo.create(
        customer_id=data.customer_id,
        status=PENDING_ALLOCATION,
        delivery_location_wkt=wkt,
        items_data=data.items,
        customer_name=data.customer_name,
        reference=new_reference(),
    )
    await session.commit()
    created = await repo.get_by_id(order.id)
    if created is None:
        raise HTTPException(status_code=500, detail="Order creation failed")
    return await _with_reservations(session, order_to_detail(created), created.id)


async def list_orders(
    session: AsyncSession, status: Optional[str] = None
) -> list[OrderRead]:
    repo = OrderRepository(session)
    orders = await repo.get_all(status=status)
    return [OrderRead.model_validate(o) for o in orders]


async def get_order(session: AsyncSession, id: UUID) -> OrderDetail:
    repo = OrderRepository(session)
    order = await repo.get_by_id(id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return await _with_reservations(session, order_to_detail(order), order.id)


async def update_order_status(
    session: AsyncSession, id: UUID, data: OrderStatusUpdate
) -> OrderRead:
    repo = OrderRepository(session)
    order = await repo.get_by_id(id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if data.status != order.status:
        allowed = ALLOWED_TRANSITIONS.get(order.status)
        if allowed is not None and data.status not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status transition from {order.status} to {data.status}",
            )
    await repo.update_status(order, data.status)
    await session.commit()
    return OrderRead.model_validate(order)
