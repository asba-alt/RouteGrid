"""GPS simulator (Phase 5).

FR-32/FR-33: vehicle positions are produced by an in-process simulator that
interpolates along the assigned route in compressed time — never by real GPS
hardware. FR-34: the current position is cached in Redis while periodic
snapshots are persisted to PostgreSQL for history. FR-36/FR-37: stop
progression drives fulfillment-group and order state.

The position maths lives in ``app.simulation.movement`` and is pure, so the
behaviour here is a thin persistence and state-update wrapper around it.
"""
import json
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import redis as redis_module
from app.core.config import settings
from app.models import FulfillmentGroup, Order, TelemetrySnapshot
from app.repositories.route_repo import (
    ACTIVE_ROUTE_STATUSES,
    ROUTE_COMPLETED,
    ROUTE_IN_PROGRESS,
    ROUTE_PLANNED,
    ROUTE_STOP_COMPLETED,
    RouteRepository,
)
from app.schemas.common import GeoPoint, wkb_to_geo_point
from app.schemas.simulation import AdvanceResponse, VehiclePositionRead
from app.services.warehouse_service import geo_point_to_wkt
from app.simulation.movement import (
    DEPOT_END_KEY,
    DEPOT_START_KEY,
    Waypoint,
    total_distance_m,
)
from app.simulation.movement import advance as advance_waypoints

GROUP_OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
GROUP_DELIVERED = "DELIVERED"
ORDER_OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
ORDER_DELIVERED = "DELIVERED"


def build_waypoints(route, depot) -> list[Waypoint]:
    """Depot -> stops in sequence -> depot.

    Stops without a location are skipped rather than failing the route; they
    still appear in ``remaining_stop_ids`` in the response.
    """
    waypoints: list[Waypoint] = []

    depot_point = None
    if depot is not None and depot.location is not None:
        depot_point = wkb_to_geo_point(depot.location)
        waypoints.append(
            Waypoint(
                key=DEPOT_START_KEY,
                lat=depot_point.lat,
                lng=depot_point.lng,
                is_stop=False,
            )
        )

    for stop in sorted(route.stops, key=lambda item: item.sequence):
        if stop.location is None:
            continue
        point = wkb_to_geo_point(stop.location)
        waypoints.append(Waypoint(key=str(stop.id), lat=point.lat, lng=point.lng))

    if depot_point is not None:
        waypoints.append(
            Waypoint(
                key=DEPOT_END_KEY,
                lat=depot_point.lat,
                lng=depot_point.lng,
                is_stop=False,
            )
        )
    return waypoints


def position_cache_key(vehicle_id: UUID) -> str:
    return f"vehicle:{vehicle_id}:position"


async def _group_and_order(session: AsyncSession, group_id):
    group = await session.get(FulfillmentGroup, group_id)
    if group is None:
        return None, None
    order = await session.get(Order, group.order_id) if group.order_id else None
    return group, order


async def _mark_out_for_delivery(session: AsyncSession, route) -> None:
    for stop in route.stops:
        group, order = await _group_and_order(session, stop.fulfillment_group_id)
        if group is not None:
            group.status = GROUP_OUT_FOR_DELIVERY
        if order is not None:
            order.status = ORDER_OUT_FOR_DELIVERY


async def _mark_delivered(session: AsyncSession, group_id) -> None:
    group, order = await _group_and_order(session, group_id)
    if group is not None:
        group.status = GROUP_DELIVERED
    if order is not None:
        # v1 materialises one fulfillment group per order, so one delivered
        # group completes the order (FR-3).
        order.status = ORDER_DELIVERED


async def _cache_position(client, route, progress) -> None:
    if client is None or route.vehicle_id is None:
        return
    payload = {
        "route_id": str(route.id),
        "lat": progress.lat,
        "lng": progress.lng,
        "simulated_at": progress.simulated_at.isoformat(),
        "simulated": True,
    }
    try:
        await client.set(position_cache_key(route.vehicle_id), json.dumps(payload))
    except Exception:
        # The cache is best-effort: PostgreSQL remains the source of truth.
        pass


async def advance(
    session: AsyncSession,
    elapsed_seconds: float,
    *,
    route_id: Optional[UUID] = None,
    persist_snapshot: bool = True,
    redis_client=None,
    now: Optional[datetime] = None,
) -> AdvanceResponse:
    repo = RouteRepository(session)

    if route_id is not None:
        route = await repo.get_by_id_with_stops(route_id)
        if route is None:
            raise HTTPException(status_code=404, detail="Route not found")
        if route.status not in ACTIVE_ROUTE_STATUSES:
            raise HTTPException(
                status_code=409,
                detail=f"Route is {route.status} and cannot be simulated",
            )
        routes = [route]
    else:
        routes = await repo.get_active_with_stops()

    client = redis_client if redis_client is not None else redis_module.redis_client
    started_clock = now or datetime.now(timezone.utc)

    positions: list[VehiclePositionRead] = []
    skipped_routes = 0

    for route in routes:
        depot = await repo.get_depot_for_route(route)
        waypoints = build_waypoints(route, depot)
        if not waypoints:
            skipped_routes += 1
            continue

        if route.started_at is None:
            route.started_at = started_clock

        progress = advance_waypoints(
            waypoints,
            elapsed_seconds,
            speed_kmh=settings.SPEED_FACTOR_KMH,
            time_compression_ratio=settings.TIME_COMPRESSION_RATIO,
            started_at=route.started_at,
        )

        completed = set(progress.completed_keys)
        for stop in route.stops:
            if str(stop.id) in completed and stop.status != ROUTE_STOP_COMPLETED:
                stop.status = ROUTE_STOP_COMPLETED
                stop.arrived_at = progress.simulated_at
                stop.completed_at = progress.simulated_at
                await _mark_delivered(session, stop.fulfillment_group_id)

        if progress.finished:
            route.status = ROUTE_COMPLETED
            route.completed_at = progress.simulated_at
        elif route.status == ROUTE_PLANNED:
            route.status = ROUTE_IN_PROGRESS
            await _mark_out_for_delivery(session, route)

        if persist_snapshot and route.vehicle_id is not None:
            session.add(
                TelemetrySnapshot(
                    vehicle_id=route.vehicle_id,
                    recorded_at=progress.simulated_at,
                    location=geo_point_to_wkt(
                        GeoPoint(lat=progress.lat, lng=progress.lng)
                    ),
                    payload={
                        "simulated": True,
                        "route_id": str(route.id),
                        "distance_travelled_m": int(progress.distance_travelled_m),
                        "total_distance_m": int(progress.total_distance_m),
                        "finished": progress.finished,
                    },
                )
            )

        await _cache_position(client, route, progress)

        ordered_stops = sorted(route.stops, key=lambda item: item.sequence)
        positions.append(
            VehiclePositionRead(
                route_id=route.id,
                vehicle_id=route.vehicle_id,
                lat=progress.lat,
                lng=progress.lng,
                simulated_at=progress.simulated_at,
                distance_travelled_m=int(round(progress.distance_travelled_m)),
                total_distance_m=int(round(progress.total_distance_m)),
                completed_stop_ids=[UUID(key) for key in progress.completed_keys],
                remaining_stop_ids=[
                    stop.id
                    for stop in ordered_stops
                    if str(stop.id) not in completed
                ],
                finished=progress.finished,
                route_status=route.status,
            )
        )

    await session.commit()
    return AdvanceResponse(advanced=positions, skipped_routes=skipped_routes)


async def current_positions(
    session: AsyncSession, redis_client=None
) -> list[VehiclePositionRead]:
    """Where every active vehicle is right now.

    Uses the cached position when one exists, and otherwise falls back to the
    last completed stop (or the depot) so the tracking map is populated the
    moment the page opens, before any simulation step has been taken.
    """
    repo = RouteRepository(session)
    routes = await repo.get_active_with_stops()
    client = redis_client if redis_client is not None else redis_module.redis_client
    positions: list[VehiclePositionRead] = []

    for route in routes:
        waypoints = build_waypoints(route, await repo.get_depot_for_route(route))
        if not waypoints:
            continue

        ordered_stops = sorted(route.stops, key=lambda item: item.sequence)
        completed_keys = [
            str(stop.id) for stop in ordered_stops if stop.status == ROUTE_STOP_COMPLETED
        ]

        lat, lng = waypoints[0].lat, waypoints[0].lng
        simulated_at = route.started_at or route.created_at
        from_cache = False

        if client is not None and route.vehicle_id is not None:
            try:
                raw = await client.get(position_cache_key(route.vehicle_id))
            except Exception:
                raw = None
            if raw:
                try:
                    cached = json.loads(raw)
                    lat, lng = float(cached["lat"]), float(cached["lng"])
                    simulated_at = datetime.fromisoformat(cached["simulated_at"])
                    from_cache = True
                except (ValueError, KeyError, TypeError):
                    from_cache = False

        if not from_cache and completed_keys:
            for waypoint in waypoints:
                if waypoint.key in completed_keys:
                    lat, lng = waypoint.lat, waypoint.lng

        completed_set = set(completed_keys)
        positions.append(
            VehiclePositionRead(
                route_id=route.id,
                vehicle_id=route.vehicle_id,
                lat=lat,
                lng=lng,
                simulated_at=simulated_at,
                distance_travelled_m=0,
                total_distance_m=int(round(total_distance_m(waypoints))),
                completed_stop_ids=[UUID(key) for key in completed_keys],
                remaining_stop_ids=[
                    stop.id
                    for stop in ordered_stops
                    if str(stop.id) not in completed_set
                ],
                finished=False,
                route_status=route.status,
            )
        )
    return positions
