"""Session-cookie authentication, CSRF origin checks, intake idempotency."""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core import auth as auth_module
from app.core.auth import (
    SESSION_COOKIE,
    get_current_user,
    hash_password,
    verify_password,
)
from app.core.config import settings
from app.core.security import csrf_protect
from app.schemas.order import OrderIntakeRequest, OrderItemCreate
from app.services import order_intake_service as svc


def make_request(method="GET", headers=None, cookies=None) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    scope = {
        "type": "http",
        "method": method,
        "path": "/",
        "headers": raw,
        "server": ("testserver", 80),
        "scheme": "http",
        "client": ("127.0.0.1", 1234),
    }
    if cookies:
        scope["headers"].append(
            (b"cookie", "; ".join(f"{k}={v}" for k, v in cookies.items()).encode())
        )
    return Request(scope)


# --- password handling ------------------------------------------------------


def test_password_hash_round_trip(monkeypatch):
    spec = hash_password("correct horse battery")
    monkeypatch.setattr(settings, "OPERATOR_PASSWORD_HASH", spec)
    monkeypatch.setattr(settings, "OPERATOR_PASSWORD", "")
    assert verify_password("correct horse battery") is True
    assert verify_password("wrong") is False


def test_plaintext_password_supported_in_development(monkeypatch):
    monkeypatch.setattr(settings, "OPERATOR_PASSWORD_HASH", "")
    monkeypatch.setattr(settings, "OPERATOR_PASSWORD", "dev-secret")
    assert verify_password("dev-secret") is True
    assert verify_password("nope") is False


def test_no_credentials_means_dev_mode(monkeypatch):
    monkeypatch.setattr(settings, "OPERATOR_PASSWORD_HASH", "")
    monkeypatch.setattr(settings, "OPERATOR_PASSWORD", "")
    assert settings.auth_enabled is False


# --- session dependency -----------------------------------------------------


async def test_dev_mode_allows_requests(monkeypatch):
    monkeypatch.setattr(settings, "OPERATOR_PASSWORD", "")
    monkeypatch.setattr(settings, "OPERATOR_PASSWORD_HASH", "")
    user = await get_current_user(make_request())
    assert user.role == "dispatcher"


async def test_missing_cookie_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "OPERATOR_PASSWORD", "dev-secret")
    with pytest.raises(HTTPException) as excinfo:
        await get_current_user(make_request())
    assert excinfo.value.status_code == 401


async def test_unknown_session_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "OPERATOR_PASSWORD", "dev-secret")
    with patch.object(auth_module, "read_session", AsyncMock(return_value=None)):
        with pytest.raises(HTTPException) as excinfo:
            await get_current_user(make_request(cookies={SESSION_COOKIE: "bogus"}))
    assert excinfo.value.status_code == 401
    assert "expired" in excinfo.value.detail.lower()


async def test_valid_session_is_accepted(monkeypatch):
    monkeypatch.setattr(settings, "OPERATOR_PASSWORD", "dev-secret")
    user_id = uuid4()
    with patch.object(
        auth_module,
        "read_session",
        AsyncMock(return_value={"id": str(user_id), "name": "operator", "role": "dispatcher"}),
    ):
        user = await get_current_user(make_request(cookies={SESSION_COOKIE: "good"}))
    assert user.id == user_id
    assert user.name == "operator"


# --- CSRF / origin validation ----------------------------------------------


async def test_safe_methods_skip_csrf(monkeypatch):
    monkeypatch.setattr(settings, "OPERATOR_PASSWORD", "dev-secret")
    await csrf_protect(make_request("GET", {"origin": "https://evil.example"}))


async def test_cross_origin_post_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "OPERATOR_PASSWORD", "dev-secret")
    monkeypatch.setattr(settings, "CORS_ORIGINS", "https://app.example")
    with pytest.raises(HTTPException) as excinfo:
        await csrf_protect(
            make_request("POST", {"origin": "https://evil.example"})
        )
    assert excinfo.value.status_code == 403


async def test_allowed_origin_post_passes(monkeypatch):
    monkeypatch.setattr(settings, "OPERATOR_PASSWORD", "dev-secret")
    monkeypatch.setattr(settings, "CORS_ORIGINS", "https://app.example")
    await csrf_protect(make_request("POST", {"origin": "https://app.example"}))


async def test_same_origin_post_passes(monkeypatch):
    monkeypatch.setattr(settings, "OPERATOR_PASSWORD", "dev-secret")
    await csrf_protect(make_request("POST", {"origin": "http://testserver"}))


async def test_forwarded_host_counts_as_same_origin(monkeypatch):
    """Behind a proxy the backend sees an internal Host, so the public host from
    X-Forwarded-Host must be honoured (browsers cannot spoof Origin)."""
    monkeypatch.setattr(settings, "OPERATOR_PASSWORD", "dev-secret")
    monkeypatch.setattr(settings, "CORS_ORIGINS", "")
    await csrf_protect(
        make_request(
            "POST",
            {"origin": "https://app.example", "x-forwarded-host": "app.example"},
        )
    )


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
