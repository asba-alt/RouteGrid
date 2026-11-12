"""Order intake workflow (Phase 3).

Accepting an order does four things inside a single transaction:
1. validate the request and its warehouse reference,
2. check stock availability against on-hand minus reserved,
3. persist the order, its items and one reservation per SKU, incrementing the
   reserved counters on the inventory rows,
4. stage an outbox event.

If any step fails the whole transaction is rolled back, so a rejected order can
never leave partial inventory holds behind.
"""
from datetime import datetime, timedelta, timezone
from typing import Mapping, Optional, Sequence

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.events.outbox import write_outbox_event
from app.repositories.idempotency_repo import IdempotencyRepository
from app.repositories.order_repo import OrderRepository
from app.repositories.reservation_repo import ReservationRepository
from app.repositories.warehouse_repo import WarehouseRepository
from app.schemas.order import (
    OrderIntakeRequest,
    OrderIntakeResponse,
    ReservationRead,
)
from app.services.order_service import (
    PENDING_ALLOCATION,
    new_reference,
    order_to_detail,
)
from app.services.warehouse_service import geo_point_to_wkt

ORDER_AGGREGATE = "order"
ORDER_CREATED_EVENT = "OrderCreated"


def aggregate_quantities(items: Sequence) -> dict[str, int]:
    """Total requested quantity per SKU.

    An order may legitimately list the same SKU more than once, so duplicate
    lines are combined rather than rejected."""
    totals: dict[str, int] = {}
    for item in items:
        totals[item.sku] = totals.get(item.sku, 0) + item.quantity
    return totals


def find_shortages(
    required: Mapping[str, int], available: Mapping[str, int]
) -> list[tuple[str, int, int]]:
    """Return (sku, requested, available) for every SKU that cannot be covered.

    This is the oversell guard from FR-14, kept pure so it can be tested without
    a database."""
    shortages = []
    for sku, quantity in sorted(required.items()):
        have = available.get(sku, 0)
        if have < quantity:
            shortages.append((sku, quantity, have))
    return shortages


def _shortage_detail(shortages: list[tuple[str, int, int]]) -> str:
    parts = [
        f"{sku} requested {requested}, available {available}"
        for sku, requested, available in shortages
    ]
    return "Insufficient inventory: " + "; ".join(parts)


def _build_response(
    order, warehouse_id, reservations
) -> OrderIntakeResponse:
    detail = order_to_detail(order)
    payload = detail.model_dump()
    payload.pop("reservations", None)  # supplied explicitly below
    return OrderIntakeResponse(
        **payload,
        warehouse_id=warehouse_id,
        reservations=[ReservationRead.model_validate(r) for r in reservations],
    )


def _reservation_expiry():
    """Holds expire after RESERVATION_TTL_MINUTES; 0 disables expiry."""
    ttl = settings.RESERVATION_TTL_MINUTES
    if ttl <= 0:
        return None
    return datetime.now(timezone.utc) + timedelta(minutes=ttl)


async def intake_order(
    session: AsyncSession,
    data: OrderIntakeRequest,
    idempotency_key: Optional[str] = None,
) -> OrderIntakeResponse:
    warehouse_repo = WarehouseRepository(session)
    order_repo = OrderRepository(session)
    reservation_repo = ReservationRepository(session)
    idempotency_repo = IdempotencyRepository(session)

    # A retry with the same key must return the original order, not a duplicate.
    if idempotency_key:
        existing_id = await idempotency_repo.get_order_id(idempotency_key)
        if existing_id is not None:
            existing = await order_repo.get_by_id(existing_id)
            if existing is not None:
                held = await reservation_repo.list_for_order(existing_id)
                warehouse_id = (
                    held[0].warehouse_id if held else data.warehouse_id
                )
                return _build_response(existing, warehouse_id, held)

    try:
        warehouse = await warehouse_repo.get_by_id(data.warehouse_id)
        if warehouse is None:
            raise HTTPException(status_code=404, detail="Warehouse not found")
        if not warehouse.operational:
            raise HTTPException(
                status_code=409,
                detail=f"Warehouse {warehouse.id} is not operational",
            )

        required = aggregate_quantities(data.items)

        # Lock the inventory rows before measuring availability so two
        # concurrent intakes cannot both pass the same stock check.
        inventory_rows = await warehouse_repo.get_inventory_for_update(
            warehouse.id, list(required)
        )
        inventory_by_sku = {row.sku: row for row in inventory_rows}
        available = {sku: row.on_hand - row.reserved for sku, row in inventory_by_sku.items()}

        shortages = find_shortages(required, available)
        if shortages:
            raise HTTPException(status_code=409, detail=_shortage_detail(shortages))

        order = await order_repo.create(
            customer_id=data.customer_id,
            status=PENDING_ALLOCATION,
            delivery_location_wkt=(
                geo_point_to_wkt(data.delivery_location)
                if data.delivery_location is not None
                else None
            ),
            items_data=data.items,
            customer_name=data.customer_name,
            reference=new_reference(),
        )

        reservations = []
        expires_at = _reservation_expiry()
        for sku, quantity in sorted(required.items()):
            inventory_by_sku[sku].reserved += quantity
            reservations.append(
                await reservation_repo.create(
                    warehouse_id=warehouse.id,
                    order_id=order.id,
                    sku=sku,
                    quantity=quantity,
                    expires_at=expires_at,
                )
            )

        if idempotency_key:
            await idempotency_repo.remember(idempotency_key, order.id)

        write_outbox_event(
            session,
            aggregate_type=ORDER_AGGREGATE,
            aggregate_id=order.id,
            event_type=ORDER_CREATED_EVENT,
            payload={
                "order_id": str(order.id),
                "warehouse_id": str(warehouse.id),
                "status": PENDING_ALLOCATION,
                "items": [
                    {"sku": sku, "quantity": quantity}
                    for sku, quantity in sorted(required.items())
                ],
            },
        )

        await session.commit()
    except HTTPException:
        await session.rollback()
        raise
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Conflict: order intake violates a database constraint",
        )
    except Exception:
        await session.rollback()
        raise

    created = await order_repo.get_by_id(order.id)
    if created is None:
        raise HTTPException(status_code=500, detail="Order intake failed")

    detail = order_to_detail(created)
    return _build_response(created, warehouse.id, reservations)
