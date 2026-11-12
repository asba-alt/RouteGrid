"""Order intake workflow (Phase 3).

The pure helpers are tested directly. The orchestration is tested with mocked
repositories so the transaction contract (commit on success, rollback on every
failure path, no partial inventory holds) can be asserted without a database.
"""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.models import OutboxEvent
from app.schemas.order import OrderIntakeRequest, OrderItemCreate
from app.services import order_intake_service as svc


def make_item(sku="A", quantity=1, weight="1.0"):
    return OrderItemCreate(sku=sku, quantity=quantity, weight_kg=Decimal(weight))


def make_request(warehouse_id, items):
    return OrderIntakeRequest(warehouse_id=warehouse_id, items=items)


def make_session():
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    return session


def make_inventory(sku, on_hand, reserved=0):
    row = MagicMock()
    row.sku = sku
    row.on_hand = on_hand
    row.reserved = reserved
    return row


def make_order(order_id):
    order = MagicMock()
    order.id = order_id
    order.customer_id = None
    order.customer_name = None
    order.reference = None
    order.status = "PENDING_ALLOCATION"
    order.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    order.items = []
    order.delivery_location = None
    return order


def make_reservation(warehouse_id, order_id, sku, quantity):
    reservation = MagicMock()
    reservation.id = uuid4()
    reservation.warehouse_id = warehouse_id
    reservation.order_id = order_id
    reservation.sku = sku
    reservation.quantity = quantity
    reservation.expires_at = None
    return reservation


@pytest.fixture
def repos():
    with patch.object(svc, "WarehouseRepository") as wh, patch.object(
        svc, "OrderRepository"
    ) as order, patch.object(svc, "ReservationRepository") as reservation:
        yield wh.return_value, order.return_value, reservation.return_value


# --- pure helpers -----------------------------------------------------------


def test_aggregate_quantities_combines_duplicate_skus():
    items = [make_item("A", 2), make_item("B", 1), make_item("A", 3)]
    assert svc.aggregate_quantities(items) == {"A": 5, "B": 1}


def test_aggregate_quantities_empty():
    assert svc.aggregate_quantities([]) == {}


def test_find_shortages_exact_stock_is_sufficient():
    assert svc.find_shortages({"A": 5}, {"A": 5}) == []


def test_find_shortages_uses_available_not_on_hand():
    assert svc.find_shortages({"A": 4}, {"A": 3}) == [("A", 4, 3)]


def test_find_shortages_reports_missing_sku_as_zero():
    assert svc.find_shortages({"A": 1}, {}) == [("A", 1, 0)]


def test_find_shortages_is_sorted_and_complete():
    assert svc.find_shortages({"B": 2, "A": 3}, {}) == [("A", 3, 0), ("B", 2, 0)]


# --- orchestration ----------------------------------------------------------


async def test_successful_intake_reserves_stock_commits_and_writes_outbox(repos):
    wh_repo, order_repo, reservation_repo = repos
    warehouse_id, order_id = uuid4(), uuid4()
    session = make_session()

    warehouse = MagicMock()
    warehouse.id = warehouse_id
    warehouse.operational = True
    wh_repo.get_by_id = AsyncMock(return_value=warehouse)

    inventory = make_inventory("A", on_hand=10, reserved=2)
    wh_repo.get_inventory_for_update = AsyncMock(return_value=[inventory])

    order_repo.create = AsyncMock(return_value=make_order(order_id))
    order_repo.get_by_id = AsyncMock(return_value=make_order(order_id))
    reservation_repo.create = AsyncMock(
        return_value=make_reservation(warehouse_id, order_id, "A", 5)
    )

    result = await svc.intake_order(
        session, make_request(warehouse_id, [make_item("A", 5)])
    )

    assert result.warehouse_id == warehouse_id
    assert result.status == "PENDING_ALLOCATION"
    assert [(r.sku, r.quantity) for r in result.reservations] == [("A", 5)]
    assert inventory.reserved == 7  # 2 already held + 5 newly reserved
    assert session.commit.await_count == 1
    assert session.rollback.await_count == 0
    assert any(
        isinstance(call.args[0], OutboxEvent) for call in session.add.call_args_list
    )


async def test_duplicate_sku_lines_produce_one_reservation(repos):
    wh_repo, order_repo, reservation_repo = repos
    warehouse_id, order_id = uuid4(), uuid4()
    session = make_session()

    warehouse = MagicMock()
    warehouse.id = warehouse_id
    warehouse.operational = True
    wh_repo.get_by_id = AsyncMock(return_value=warehouse)
    inventory = make_inventory("A", on_hand=10)
    wh_repo.get_inventory_for_update = AsyncMock(return_value=[inventory])
    order_repo.create = AsyncMock(return_value=make_order(order_id))
    order_repo.get_by_id = AsyncMock(return_value=make_order(order_id))
    reservation_repo.create = AsyncMock(
        return_value=make_reservation(warehouse_id, order_id, "A", 5)
    )

    result = await svc.intake_order(
        session, make_request(warehouse_id, [make_item("A", 2), make_item("A", 3)])
    )

    assert len(result.reservations) == 1
    assert inventory.reserved == 5
    assert reservation_repo.create.await_count == 1


async def test_missing_warehouse_returns_404_and_rolls_back(repos):
    wh_repo, order_repo, _ = repos
    session = make_session()
    wh_repo.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as excinfo:
        await svc.intake_order(session, make_request(uuid4(), [make_item()]))

    assert excinfo.value.status_code == 404
    assert session.rollback.await_count == 1
    assert session.commit.await_count == 0
    order_repo.create.assert_not_called()


async def test_non_operational_warehouse_returns_409(repos):
    wh_repo, order_repo, _ = repos
    session = make_session()
    warehouse = MagicMock()
    warehouse.id = uuid4()
    warehouse.operational = False
    wh_repo.get_by_id = AsyncMock(return_value=warehouse)

    with pytest.raises(HTTPException) as excinfo:
        await svc.intake_order(session, make_request(warehouse.id, [make_item()]))

    assert excinfo.value.status_code == 409
    assert "not operational" in excinfo.value.detail
    assert session.rollback.await_count == 1
    order_repo.create.assert_not_called()


async def test_insufficient_stock_returns_409_and_creates_nothing(repos):
    wh_repo, order_repo, reservation_repo = repos
    warehouse_id = uuid4()
    session = make_session()

    warehouse = MagicMock()
    warehouse.id = warehouse_id
    warehouse.operational = True
    wh_repo.get_by_id = AsyncMock(return_value=warehouse)
    inventory = make_inventory("A", on_hand=5, reserved=3)  # only 2 available
    wh_repo.get_inventory_for_update = AsyncMock(return_value=[inventory])

    with pytest.raises(HTTPException) as excinfo:
        await svc.intake_order(session, make_request(warehouse_id, [make_item("A", 4)]))

    assert excinfo.value.status_code == 409
    assert "Insufficient inventory" in excinfo.value.detail
    assert inventory.reserved == 3  # unchanged: no partial hold
    order_repo.create.assert_not_called()
    reservation_repo.create.assert_not_called()
    assert session.rollback.await_count == 1
    assert session.commit.await_count == 0


async def test_integrity_error_during_write_returns_409_and_rolls_back(repos):
    wh_repo, order_repo, _ = repos
    warehouse_id = uuid4()
    session = make_session()

    warehouse = MagicMock()
    warehouse.id = warehouse_id
    warehouse.operational = True
    wh_repo.get_by_id = AsyncMock(return_value=warehouse)
    wh_repo.get_inventory_for_update = AsyncMock(
        return_value=[make_inventory("A", on_hand=10)]
    )
    order_repo.create = AsyncMock(
        side_effect=IntegrityError("INSERT INTO \"order\"", {}, Exception("boom"))
    )

    with pytest.raises(HTTPException) as excinfo:
        await svc.intake_order(session, make_request(warehouse_id, [make_item("A", 1)]))

    assert excinfo.value.status_code == 409
    assert session.rollback.await_count == 1
    assert session.commit.await_count == 0


async def test_update_status_rejects_cancellation_after_dispatch(repos):
    """FR-4 is enforced by the existing status endpoint, not a new code path."""
    from app.repositories.order_repo import OrderRepository
    from app.schemas.order import OrderStatusUpdate
    from app.services import order_service

    session = make_session()
    order = make_order(uuid4())
    order.status = "OUT_FOR_DELIVERY"

    with patch.object(OrderRepository, "get_by_id", AsyncMock(return_value=order)):
        with pytest.raises(HTTPException) as excinfo:
            await order_service.update_order_status(
                session, order.id, OrderStatusUpdate(status="CANCELLED")
            )

    assert excinfo.value.status_code == 400
    assert session.commit.await_count == 0


# --- review gaps: reservation fields, outbox payload, generic failure -------


async def test_reservation_carries_warehouse_order_sku_and_no_group(repos, monkeypatch):
    from app.core.config import settings

    # Expiry is configuration-driven; pin it so this test is deterministic.
    monkeypatch.setattr(settings, "RESERVATION_TTL_MINUTES", 0)
    wh_repo, order_repo, reservation_repo = repos
    warehouse_id, order_id = uuid4(), uuid4()
    session = make_session()

    warehouse = MagicMock()
    warehouse.id = warehouse_id
    warehouse.operational = True
    wh_repo.get_by_id = AsyncMock(return_value=warehouse)
    wh_repo.get_inventory_for_update = AsyncMock(
        return_value=[make_inventory("A", on_hand=10)]
    )
    order_repo.create = AsyncMock(return_value=make_order(order_id))
    order_repo.get_by_id = AsyncMock(return_value=make_order(order_id))
    reservation_repo.create = AsyncMock(
        return_value=make_reservation(warehouse_id, order_id, "A", 5)
    )

    await svc.intake_order(session, make_request(warehouse_id, [make_item("A", 5)]))

    # No fulfillment group exists yet (that is Phase 4), so the reservation is
    # tied to the order only, and expiry policy is still an open question.
    reservation_repo.create.assert_awaited_once_with(
        warehouse_id=warehouse_id,
        order_id=order_id,
        sku="A",
        quantity=5,
        expires_at=None,
    )


async def test_outbox_event_describes_the_intake(repos):
    wh_repo, order_repo, reservation_repo = repos
    warehouse_id, order_id = uuid4(), uuid4()
    session = make_session()

    warehouse = MagicMock()
    warehouse.id = warehouse_id
    warehouse.operational = True
    wh_repo.get_by_id = AsyncMock(return_value=warehouse)
    wh_repo.get_inventory_for_update = AsyncMock(
        return_value=[make_inventory("A", on_hand=10)]
    )
    order_repo.create = AsyncMock(return_value=make_order(order_id))
    order_repo.get_by_id = AsyncMock(return_value=make_order(order_id))
    reservation_repo.create = AsyncMock(
        return_value=make_reservation(warehouse_id, order_id, "A", 5)
    )

    await svc.intake_order(session, make_request(warehouse_id, [make_item("A", 5)]))

    events = [
        call.args[0]
        for call in session.add.call_args_list
        if isinstance(call.args[0], OutboxEvent)
    ]
    assert len(events) == 1
    event = events[0]
    assert event.aggregate_type == "order"
    assert event.aggregate_id == order_id
    assert event.event_type == "OrderCreated"
    assert event.published is False
    assert event.payload["warehouse_id"] == str(warehouse_id)
    assert event.payload["status"] == "PENDING_ALLOCATION"
    assert event.payload["items"] == [{"sku": "A", "quantity": 5}]


async def test_unexpected_error_rolls_back_and_propagates(repos):
    """A non-HTTP failure must roll back and surface as a 500, not a silent 201."""
    wh_repo, order_repo, _ = repos
    warehouse_id = uuid4()
    session = make_session()

    warehouse = MagicMock()
    warehouse.id = warehouse_id
    warehouse.operational = True
    wh_repo.get_by_id = AsyncMock(return_value=warehouse)
    wh_repo.get_inventory_for_update = AsyncMock(
        return_value=[make_inventory("A", on_hand=10)]
    )
    order_repo.create = AsyncMock(side_effect=RuntimeError("connection lost"))

    with pytest.raises(RuntimeError):
        await svc.intake_order(session, make_request(warehouse_id, [make_item("A", 1)]))

    assert session.rollback.await_count == 1
    assert session.commit.await_count == 0
