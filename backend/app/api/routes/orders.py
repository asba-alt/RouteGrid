from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.db.session import get_db
from app.schemas.order import (
    OrderCreate,
    OrderDetail,
    OrderIntakeRequest,
    OrderIntakeResponse,
    OrderRead,
    OrderStatusUpdate,
)
from app.services import order_intake_service, order_service

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


@router.post("", response_model=OrderDetail, status_code=http_status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> OrderDetail:
    return await order_service.create_order(db, payload)


@router.get("", response_model=list[OrderRead])
async def list_orders(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[OrderRead]:
    return await order_service.list_orders(db, status)


@router.post(
    "/intake",
    response_model=OrderIntakeResponse,
    status_code=http_status.HTTP_201_CREATED,
)
async def intake_order(
    payload: OrderIntakeRequest,
    idempotency_key: Optional[str] = Header(
        default=None,
        alias="Idempotency-Key",
        description="Retry-safe key: repeating it returns the original order.",
    ),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> OrderIntakeResponse:
    """Order intake: validate, reserve inventory, persist, emit outbox event.

    Declared before ``/{order_id}`` so the literal path is not parsed as a UUID.
    """
    return await order_intake_service.intake_order(db, payload, idempotency_key)


@router.get("/{order_id}", response_model=OrderDetail)
async def get_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> OrderDetail:
    return await order_service.get_order(db, order_id)


@router.patch("/{order_id}/status", response_model=OrderRead)
async def update_order_status(
    order_id: UUID,
    payload: OrderStatusUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> OrderRead:
    return await order_service.update_order_status(db, order_id, payload)
