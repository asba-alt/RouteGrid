"""Optimization service: pure helpers, and persistence driven by the real solver.

Repositories are mocked, so these tests verify orchestration and the objects the
service stages on the session. They do not prove anything about PostgreSQL.
"""
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from geoalchemy2.elements import WKBElement
from shapely import wkb as shapely_wkb
from shapely.geometry import Point

from app.models import OutboxEvent, Route, RouteStop
from app.services import optimization_service as svc


def make_wkb(lat, lng):
    return WKBElement(shapely_wkb.dumps(Point(lng, lat)), srid=4326)


def make_item(quantity, weight):
    item = MagicMock()
    item.quantity = quantity
    item.weight_kg = Decimal(weight)
    return item


def make_order(lat=17.39, lng=78.49):
    order = MagicMock()
    order.id = uuid4()
    order.status = "PENDING_ALLOCATION"
    order.delivery_location = make_wkb(lat, lng)
    order.items = [make_item(2, "1.5")]
    return order


def make_group():
    group = MagicMock()
    group.id = uuid4()
    group.status = "PENDING_ALLOCATION"
    group.assigned_route_id = None
    return group


def make_vehicle(max_weight_kg="1000"):
    vehicle = MagicMock()
    vehicle.id = uuid4()
    vehicle.max_weight_kg = Decimal(max_weight_kg)
    return vehicle


def make_depot(lat=17.3850, lng=78.4867):
    depot = MagicMock()
    depot.id = uuid4()
    depot.location = make_wkb(lat, lng)
    return depot


def make_session():
    """A stand-in session whose flush() applies the uuid4 column defaults."""
    session = MagicMock()
    added = []
    session.add = MagicMock(side_effect=added.append)

    async def flush():
        for obj in added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid4()

    session.flush = AsyncMock(side_effect=flush)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()
    return session, added


@pytest.fixture
def patched():
    with patch.object(svc, "OrderRepository") as orders, patch.object(
        svc, "FulfillmentGroupRepository"
    ) as groups, patch.object(svc, "VehicleRepository") as vehicles, patch.object(
        svc, "ReservationRepository"
    ) as reservations:
        yield (
            orders.return_value,
            groups.return_value,
            vehicles.return_value,
            reservations.return_value,
        )


# --- pure helpers -----------------------------------------------------------


def test_item_weight_is_quantity_times_unit_weight():
    assert svc.item_weight_g(3, Decimal("1.5")) == 4500
    assert svc.item_weight_g(1, Decimal("0.25")) == 250


def test_group_demand_sums_every_line():
    assert svc.group_demand_g([make_item(2, "1.0"), make_item(3, "0.5")]) == 3500


def test_estimated_travel_time_uses_the_configured_speed_factor():
    """FR-29: travel time is distance / configured speed."""
    from app.core.config import settings

    expected = int(round(40_000 / 1000 / settings.SPEED_FACTOR_KMH * 3600))
    assert svc.estimated_travel_time_seconds(40_000) == expected
    assert svc.estimated_travel_time_seconds(0) == 0


def test_default_solver_budget_is_configurable_and_small():
    """The default must come from settings, not a hardcoded 5 seconds."""
    from app.core.config import settings
    from app.schemas.optimization import BatchSolveRequest

    assert BatchSolveRequest().time_limit_seconds == settings.OPTIMIZER_TIME_LIMIT_SECONDS
    assert settings.OPTIMIZER_TIME_LIMIT_SECONDS <= 5


# --- orchestration ----------------------------------------------------------


async def test_solve_batch_persists_route_stops_and_allocates(patched):
    order_repo, group_repo, vehicle_repo, _ = patched
    session, added = make_session()

    order = make_order()
    group = make_group()
    vehicle = make_vehicle("1000")  # 1,000,000 g, far above the 3000 g demand
    depot = make_depot()

    order_repo.get_by_status_with_items = AsyncMock(return_value=[order])
    group_repo.get_for_order = AsyncMock(return_value=group)
    vehicle_repo.get_routable_with_depot = AsyncMock(return_value=[(vehicle, depot)])

    response = await svc.solve_batch(session, use_local_search=False)

    assert response.solved is True
    assert response.eligible_order_count == 1
    assert response.operational_vehicle_count == 1
    assert response.unassigned_fulfillment_group_ids == []
    assert len(response.routes) == 1
    assert response.routes[0].fulfillment_group_ids == [group.id]
    assert response.routes[0].vehicle_id == vehicle.id
    assert response.routes[0].travel_time_seconds > 0
    assert response.total_travel_time_seconds > 0

    routes = [obj for obj in added if isinstance(obj, Route)]
    stops = [obj for obj in added if isinstance(obj, RouteStop)]
    assert len(routes) == 1
    assert len(stops) == 1
    assert routes[0].vehicle_id == vehicle.id
    assert routes[0].status == "PLANNED"
    assert stops[0].sequence == 1
    assert stops[0].fulfillment_group_id == group.id
    assert stops[0].route_id == routes[0].id
    assert stops[0].status == "PENDING"

    assert group.assigned_route_id == routes[0].id
    assert group.status == "ALLOCATED"
    assert order.status == "ALLOCATED"
    assert session.commit.await_count == 1
    assert session.rollback.await_count == 0
    assert any(isinstance(obj, OutboxEvent) for obj in added)


async def test_missing_group_is_created_and_holds_are_attached(patched):
    order_repo, group_repo, vehicle_repo, reservation_repo = patched
    session, _ = make_session()

    order = make_order()
    group = make_group()
    warehouse_id = uuid4()

    order_repo.get_by_status_with_items = AsyncMock(return_value=[order])
    group_repo.get_for_order = AsyncMock(return_value=None)
    group_repo.create_for_order = AsyncMock(return_value=group)
    reservation_repo.get_warehouse_id_for_order = AsyncMock(return_value=warehouse_id)
    reservation_repo.attach_to_group = AsyncMock(return_value=1)
    vehicle_repo.get_routable_with_depot = AsyncMock(
        return_value=[(make_vehicle(), make_depot())]
    )

    await svc.solve_batch(session, use_local_search=False)

    group_repo.create_for_order.assert_awaited_once()
    args = group_repo.create_for_order.await_args.args
    assert args[0] is order
    assert args[1] == warehouse_id
    assert args[2].startswith("SRID=4326;POINT(")
    reservation_repo.attach_to_group.assert_awaited_once_with(order.id, group.id)


async def test_unservable_delivery_stays_pending_and_creates_no_route(patched):
    order_repo, group_repo, vehicle_repo, _ = patched
    session, added = make_session()

    order = make_order()
    group = make_group()

    order_repo.get_by_status_with_items = AsyncMock(return_value=[order])
    group_repo.get_for_order = AsyncMock(return_value=group)
    # 1 kg capacity cannot carry the 3 kg order.
    vehicle_repo.get_routable_with_depot = AsyncMock(
        return_value=[(make_vehicle("1"), make_depot())]
    )

    response = await svc.solve_batch(session, use_local_search=False)

    assert response.solved is True
    assert response.routes == []
    assert response.unassigned_fulfillment_group_ids == [group.id]
    assert order.status == "PENDING_ALLOCATION"
    assert group.status == "PENDING_ALLOCATION"
    assert not [obj for obj in added if isinstance(obj, Route)]
    assert session.commit.await_count == 1


async def test_orders_without_a_delivery_location_are_skipped(patched):
    order_repo, group_repo, vehicle_repo, _ = patched
    session, _ = make_session()

    located = make_order()
    unlocated = make_order()
    unlocated.delivery_location = None

    order_repo.get_by_status_with_items = AsyncMock(return_value=[located, unlocated])
    group_repo.get_for_order = AsyncMock(return_value=make_group())
    vehicle_repo.get_routable_with_depot = AsyncMock(
        return_value=[(make_vehicle(), make_depot())]
    )

    response = await svc.solve_batch(session, use_local_search=False)

    assert response.skipped_orders_without_location == 1
    assert response.eligible_order_count == 1


async def test_no_operational_vehicles_reports_unsolved(patched):
    order_repo, group_repo, vehicle_repo, _ = patched
    session, _ = make_session()

    group = make_group()
    order_repo.get_by_status_with_items = AsyncMock(return_value=[make_order()])
    group_repo.get_for_order = AsyncMock(return_value=group)
    vehicle_repo.get_routable_with_depot = AsyncMock(return_value=[])

    response = await svc.solve_batch(session, use_local_search=False)

    assert response.solved is False
    assert response.operational_vehicle_count == 0
    assert response.unassigned_fulfillment_group_ids == [group.id]


async def test_failure_rolls_back_and_propagates(patched):
    order_repo, _, _, _ = patched
    session, _ = make_session()
    order_repo.get_by_status_with_items = AsyncMock(side_effect=RuntimeError("db down"))

    with pytest.raises(RuntimeError):
        await svc.solve_batch(session, use_local_search=False)

    assert session.rollback.await_count == 1
    assert session.commit.await_count == 0


async def test_only_pending_allocation_orders_are_queried(patched):
    """FR-24 and item 8: delivered/cancelled work must never be re-planned."""
    order_repo, group_repo, vehicle_repo, _ = patched
    session, _ = make_session()

    order_repo.get_by_status_with_items = AsyncMock(return_value=[])
    vehicle_repo.get_routable_with_depot = AsyncMock(return_value=[])

    await svc.solve_batch(session, use_local_search=False)

    order_repo.get_by_status_with_items.assert_awaited_once_with("PENDING_ALLOCATION")
