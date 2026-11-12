"""Simulator service: orchestration, state updates and edge cases.

Repositories and the session are mocked, so this verifies the objects and status
changes the service produces — not PostgreSQL persistence or real Redis.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from geoalchemy2.elements import WKBElement
from shapely import wkb as shapely_wkb
from shapely.geometry import Point

from app.models import FulfillmentGroup, Order, TelemetrySnapshot
from app.repositories.route_repo import (
    ROUTE_COMPLETED,
    ROUTE_IN_PROGRESS,
    ROUTE_PLANNED,
)
from app.services import simulation_service as svc
from app.simulation.movement import DEPOT_END_KEY, DEPOT_START_KEY

START = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)


def make_wkb(lat, lng):
    return WKBElement(shapely_wkb.dumps(Point(lng, lat)), srid=4326)


def make_stop(sequence, lat, lng, group_id):
    stop = MagicMock()
    stop.id = uuid4()
    stop.sequence = sequence
    stop.status = "PENDING"
    stop.location = make_wkb(lat, lng) if lat is not None else None
    stop.arrived_at = None
    stop.completed_at = None
    stop.fulfillment_group_id = group_id
    return stop


def make_route(stops, vehicle_id=None, status=ROUTE_PLANNED, started_at=None):
    route = MagicMock()
    route.id = uuid4()
    route.status = status
    route.vehicle_id = vehicle_id
    route.started_at = started_at
    route.completed_at = None
    route.stops = stops
    return route


def make_depot(lat=0.0, lng=0.0):
    depot = MagicMock()
    depot.location = make_wkb(lat, lng)
    return depot


def make_group(order_id):
    group = MagicMock()
    group.id = uuid4()
    group.order_id = order_id
    group.status = "ALLOCATED"
    return group


def make_session(groups=None, orders=None):
    session = MagicMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()
    groups = groups or {}
    orders = orders or {}

    async def get(model, key):
        if model is FulfillmentGroup:
            return groups.get(key)
        if model is Order:
            return orders.get(key)
        return None

    session.get = AsyncMock(side_effect=get)
    return session


@pytest.fixture
def repo():
    with patch.object(svc, "RouteRepository") as repository:
        yield repository.return_value


def standalone_route(group_id):
    """A two-stop route with a depot at the origin."""
    vehicle_id = uuid4()
    stops = [
        make_stop(1, 0.0, 0.01, group_id),
        make_stop(2, 0.0, 0.02, group_id),
    ]
    route = make_route(stops, vehicle_id=vehicle_id, started_at=START)
    return route, stops, vehicle_id


# --- waypoint construction --------------------------------------------------


def test_build_waypoints_wraps_stops_between_the_depot_in_sequence_order():
    group_id = uuid4()
    stops = [make_stop(2, 0.0, 0.02, group_id), make_stop(1, 0.0, 0.01, group_id)]

    waypoints = svc.build_waypoints(make_route(stops), make_depot())

    assert waypoints[0].key == DEPOT_START_KEY
    assert waypoints[0].is_stop is False
    assert waypoints[-1].key == DEPOT_END_KEY
    assert waypoints[-1].is_stop is False
    # sequence wins over list order
    assert [w.key for w in waypoints[1:-1]] == [str(stops[1].id), str(stops[0].id)]


def test_build_waypoints_skips_stops_without_a_location():
    group_id = uuid4()
    stops = [make_stop(1, 0.0, 0.01, group_id), make_stop(2, None, None, group_id)]

    waypoints = svc.build_waypoints(make_route(stops), make_depot())

    assert [w.key for w in waypoints] == [
        DEPOT_START_KEY,
        str(stops[0].id),
        DEPOT_END_KEY,
    ]


def test_build_waypoints_without_a_depot_uses_stops_only():
    stops = [make_stop(1, 0.0, 0.01, uuid4())]

    waypoints = svc.build_waypoints(make_route(stops), None)

    assert [w.key for w in waypoints] == [str(stops[0].id)]
    assert all(w.is_stop for w in waypoints)


# --- error handling ---------------------------------------------------------


async def test_unknown_route_returns_404(repo):
    session = make_session()
    repo.get_by_id_with_stops = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as excinfo:
        await svc.advance(session, 5, route_id=uuid4())

    assert excinfo.value.status_code == 404
    assert session.commit.await_count == 0


async def test_completed_route_cannot_be_simulated(repo):
    session = make_session()
    repo.get_by_id_with_stops = AsyncMock(
        return_value=make_route([], status=ROUTE_COMPLETED)
    )

    with pytest.raises(HTTPException) as excinfo:
        await svc.advance(session, 5, route_id=uuid4())

    assert excinfo.value.status_code == 409
    assert "cannot be simulated" in excinfo.value.detail


# --- normal progression -----------------------------------------------------


async def test_advance_updates_route_state_snapshot_and_cache(repo):
    group_id, order_id = uuid4(), uuid4()
    group = make_group(order_id)
    order = MagicMock()
    order.status = "ALLOCATED"
    session = make_session(groups={group_id: group}, orders={order_id: order})

    route, stops, vehicle_id = standalone_route(group_id)
    repo.get_by_id_with_stops = AsyncMock(return_value=route)
    repo.get_depot_for_route = AsyncMock(return_value=make_depot())

    client = MagicMock()
    client.set = AsyncMock()

    result = await svc.advance(session, 1, route_id=route.id, redis_client=client)

    assert len(result.advanced) == 1
    position = result.advanced[0]
    assert position.route_id == route.id
    assert position.vehicle_id == vehicle_id
    assert position.simulated is True  # FR-35
    assert position.finished is False
    assert position.route_status == ROUTE_IN_PROGRESS
    assert position.simulated_at == START + timedelta(seconds=60)
    assert 0 < position.distance_travelled_m < position.total_distance_m

    assert route.status == ROUTE_IN_PROGRESS
    assert route.started_at == START
    assert group.status == "OUT_FOR_DELIVERY"
    assert order.status == "OUT_FOR_DELIVERY"
    assert all(stop.status == "PENDING" for stop in stops)

    snapshots = [
        call.args[0]
        for call in session.add.call_args_list
        if isinstance(call.args[0], TelemetrySnapshot)
    ]
    assert len(snapshots) == 1
    assert snapshots[0].vehicle_id == vehicle_id
    assert snapshots[0].recorded_at == position.simulated_at
    assert snapshots[0].payload["simulated"] is True

    client.set.assert_awaited_once()
    assert svc.position_cache_key(vehicle_id) == f"vehicle:{vehicle_id}:position"
    assert session.commit.await_count == 1


async def test_route_completion_marks_everything_delivered(repo):
    group_id, order_id = uuid4(), uuid4()
    group = make_group(order_id)
    order = MagicMock()
    order.status = "ALLOCATED"
    session = make_session(groups={group_id: group}, orders={order_id: order})

    route, stops, _ = standalone_route(group_id)
    repo.get_by_id_with_stops = AsyncMock(return_value=route)
    repo.get_depot_for_route = AsyncMock(return_value=make_depot())

    result = await svc.advance(session, 86_400, route_id=route.id, redis_client=False)

    position = result.advanced[0]
    assert position.finished is True
    assert position.route_status == ROUTE_COMPLETED
    assert len(position.completed_stop_ids) == 2
    assert position.remaining_stop_ids == []
    assert route.completed_at is not None

    assert all(stop.status == "COMPLETED" for stop in stops)
    assert all(stop.arrived_at == position.simulated_at for stop in stops)
    assert all(stop.completed_at == position.simulated_at for stop in stops)
    assert group.status == "DELIVERED"
    assert order.status == "DELIVERED"


async def test_stop_without_coordinates_stays_pending_and_remaining(repo):
    group_id = uuid4()
    session = make_session(groups={group_id: make_group(uuid4())})
    route, stops, _ = standalone_route(group_id)
    stops[1].location = None

    repo.get_by_id_with_stops = AsyncMock(return_value=route)
    repo.get_depot_for_route = AsyncMock(return_value=make_depot())

    result = await svc.advance(session, 86_400, route_id=route.id, redis_client=False)

    position = result.advanced[0]
    assert stops[0].id in position.completed_stop_ids
    assert stops[1].id in position.remaining_stop_ids
    assert stops[1].status == "PENDING"


async def test_route_with_no_coordinates_at_all_is_skipped(repo):
    session = make_session()
    route = make_route([make_stop(1, None, None, uuid4())])
    repo.get_active_with_stops = AsyncMock(return_value=[route])
    repo.get_depot_for_route = AsyncMock(return_value=None)

    result = await svc.advance(session, 5)

    assert result.advanced == []
    assert result.skipped_routes == 1


# --- resilience -------------------------------------------------------------


async def test_advance_works_without_a_redis_client(repo):
    session = make_session(groups={}, orders={})
    route, _, _ = standalone_route(uuid4())
    repo.get_by_id_with_stops = AsyncMock(return_value=route)
    repo.get_depot_for_route = AsyncMock(return_value=make_depot())

    result = await svc.advance(session, 1, route_id=route.id)

    assert len(result.advanced) == 1
    assert session.commit.await_count == 1


async def test_redis_failure_does_not_break_the_step(repo):
    session = make_session(groups={}, orders={})
    route, _, _ = standalone_route(uuid4())
    repo.get_by_id_with_stops = AsyncMock(return_value=route)
    repo.get_depot_for_route = AsyncMock(return_value=make_depot())

    client = MagicMock()
    client.set = AsyncMock(side_effect=RuntimeError("redis down"))

    result = await svc.advance(session, 1, route_id=route.id, redis_client=client)

    assert len(result.advanced) == 1
    assert session.commit.await_count == 1


async def test_snapshot_persistence_can_be_disabled(repo):
    session = make_session(groups={}, orders={})
    route, _, _ = standalone_route(uuid4())
    repo.get_by_id_with_stops = AsyncMock(return_value=route)
    repo.get_depot_for_route = AsyncMock(return_value=make_depot())

    await svc.advance(
        session, 1, route_id=route.id, persist_snapshot=False, redis_client=False
    )

    assert not [
        call.args[0]
        for call in session.add.call_args_list
        if isinstance(call.args[0], TelemetrySnapshot)
    ]


async def test_advancing_all_active_routes_uses_the_active_query(repo):
    session = make_session()
    repo.get_active_with_stops = AsyncMock(return_value=[])

    result = await svc.advance(session, 5)

    repo.get_active_with_stops.assert_awaited_once()
    assert result.advanced == []
    assert result.skipped_routes == 0
