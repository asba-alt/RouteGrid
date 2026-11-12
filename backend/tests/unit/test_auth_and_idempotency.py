"""Authentication seam, intake idempotency and reservation expiry."""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core.auth import get_current_user
from app.core.config import settings
from app.schemas.order import OrderIntakeRequest, OrderItemCreate
from app.services import order_intake_service as svc


def make_request(headers=None) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "method": "GET", "path": "/", "headers": raw})


# --- authentication ---------------------------------------------------------


async def test_auth_disabled_allows_requests(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "")
    user = await get_current_user(make_request())
    assert user.role == "dispatcher"


async def test_auth_requires_a_key_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "s3cret")
    with pytest.raises(HTTPException) as excinfo:
        await get_current_user(make_request())
    assert excinfo.value.status_code == 401


async def test_auth_rejects_a_wrong_key(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "s3cret")
    with pytest.raises(HTTPException) as excinfo:
        await get_current_user(make_request({"X-API-Key": "nope"}))
    assert excinfo.value.status_code == 401


async def test_auth_accepts_the_correct_key(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "s3cret")
    user = await get_current_user(make_request({"X-API-Key": "s3cret"}))
    assert user.name == "Dev Operator"


# --- idempotent intake ------------------------------------------------------


def make_order(order_id):
    order = MagicMock()
    order.id = order_id
    order.customer_id = None
    order.customer_name = "Sri Lakshmi Traders"
    order.reference = "ORD-TEST0001"
    order.status = "PENDING_ALLOCATION"
    order.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    order.items = []
    order.delivery_location = None
    return order


def make_reservation(warehouse_id, order_id):
    reservation = MagicMock()
    reservation.id = uuid4()
    reservation.warehouse_id = warehouse_id
    reservation.order_id = order_id
    reservation.sku = "Grocery-Rice-5kg"
    reservation.quantity = 2
    reservation.expires_at = None
    return reservation


async def test_replaying_a_key_returns_the_original_order():
    """A retried POST must not create a second order."""
    warehouse_id, order_id = uuid4(), uuid4()
    session = MagicMock()
    session.commit = AsyncMock()

    request = OrderIntakeRequest(
        warehouse_id=warehouse_id,
        items=[OrderItemCreate(sku="Grocery-Rice-5kg", quantity=2, weight_kg=Decimal("1"))],
    )

    with patch.object(svc, "IdempotencyRepository") as Idem, patch.object(
        svc, "OrderRepository"
    ) as Orders, patch.object(svc, "ReservationRepository") as Reservations:
        Idem.return_value.get_order_id = AsyncMock(return_value=order_id)
        Orders.return_value.get_by_id = AsyncMock(return_value=make_order(order_id))
        Orders.return_value.create = AsyncMock()
        Reservations.return_value.list_for_order = AsyncMock(
            return_value=[make_reservation(warehouse_id, order_id)]
        )

        result = await svc.intake_order(session, request, idempotency_key="retry-1")

    assert result.id == order_id
    assert result.reference == "ORD-TEST0001"
    Orders.return_value.create.assert_not_called()
    session.commit.assert_not_awaited()


async def test_absent_key_skips_the_idempotency_lookup():
    session = MagicMock()
    session.rollback = AsyncMock()
    session.commit = AsyncMock()
    request = OrderIntakeRequest(
        warehouse_id=uuid4(),
        items=[OrderItemCreate(sku="X", quantity=1, weight_kg=Decimal("1"))],
    )
    with patch.object(svc, "IdempotencyRepository") as Idem, patch.object(
        svc, "WarehouseRepository"
    ) as Warehouses:
        Warehouses.return_value.get_by_id = AsyncMock(return_value=None)
        with pytest.raises(HTTPException):
            await svc.intake_order(session, request)
    Idem.return_value.get_order_id.assert_not_called()


# --- reservation expiry -----------------------------------------------------


def test_expiry_is_none_when_ttl_disabled(monkeypatch):
    monkeypatch.setattr(settings, "RESERVATION_TTL_MINUTES", 0)
    assert svc._reservation_expiry() is None


def test_expiry_is_set_when_ttl_configured(monkeypatch):
    monkeypatch.setattr(settings, "RESERVATION_TTL_MINUTES", 30)
    expiry = svc._reservation_expiry()
    assert expiry is not None
    assert expiry > datetime.now(timezone.utc)
