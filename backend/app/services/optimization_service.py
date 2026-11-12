"""Batch route optimization (Phase 4).

One pass does five things:
1. collect orders awaiting allocation that have a delivery location,
2. materialise the fulfillment group each order will be routed as,
3. collect operational vehicles with routable depots,
4. solve the CVRP jointly over all deliveries and vehicles,
5. persist one route per used vehicle with its ordered stops and mark the
   assigned groups and their orders as allocated.

Everything is committed together or rolled back together. Deliveries the solver
cannot serve are reported as unassigned and deliberately left in
``PENDING_ALLOCATION`` so the next batch can retry them.
"""
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.events.outbox import write_outbox_event
from app.models import Route, RouteStop
from app.optimization.cvrp import (
    Delivery,
    Location,
    VehicleSpec,
    solve_cvrp,
)
from app.optimization.geo import travel_time_seconds
from app.repositories.fulfillment_repo import FulfillmentGroupRepository
from app.repositories.fleet_repo import VehicleRepository
from app.repositories.order_repo import OrderRepository
from app.repositories.reservation_repo import ReservationRepository
from app.repositories.route_repo import ROUTE_PLANNED, ROUTE_STOP_PENDING
from app.schemas.common import GeoPoint, wkb_to_geo_point
from app.schemas.optimization import BatchSolveResponse, PlannedRouteRead
from app.services.order_service import PENDING_ALLOCATION
from app.services.warehouse_service import geo_point_to_wkt

ORDER_ALLOCATED = "ALLOCATED"
GROUP_ALLOCATED = "ALLOCATED"

ROUTE_AGGREGATE = "route"
ROUTE_PLANNED_EVENT = "RoutePlanned"

GRAMS_PER_KG = 1000


def item_weight_g(quantity: int, weight_kg) -> int:
    """Line weight in grams.

    ASSUMPTION: ``order_item.weight_kg`` is the weight of a single unit, so a
    line weighs ``quantity * weight_kg``. The specification does not state which
    convention applies; this function is the only place it is encoded, so the
    choice is a one-line change if it is wrong.
    """
    return int(round(float(quantity) * float(weight_kg) * GRAMS_PER_KG))


def group_demand_g(items) -> int:
    """Total weight a fulfillment group asks a vehicle to carry."""
    return sum(item_weight_g(item.quantity, item.weight_kg) for item in items)


def estimated_travel_time_seconds(distance_m: int) -> int:
    """FR-29 travel-time approximation using the configured speed factor."""
    return int(round(travel_time_seconds(distance_m, settings.SPEED_FACTOR_KMH)))


async def solve_batch(
    session: AsyncSession,
    *,
    time_limit_seconds: int = settings.OPTIMIZER_TIME_LIMIT_SECONDS,
    use_local_search: bool = True,
) -> BatchSolveResponse:
    order_repo = OrderRepository(session)
    group_repo = FulfillmentGroupRepository(session)
    vehicle_repo = VehicleRepository(session)
    reservation_repo = ReservationRepository(session)

    try:
        pending_orders = await order_repo.get_by_status_with_items(PENDING_ALLOCATION)
        eligible_orders = [o for o in pending_orders if o.delivery_location is not None]
        skipped_without_location = len(pending_orders) - len(eligible_orders)

        pairs = []
        for order in eligible_orders:
            group = await group_repo.get_for_order(order.id)
            if group is None:
                destination = wkb_to_geo_point(order.delivery_location)
                warehouse_id = await reservation_repo.get_warehouse_id_for_order(
                    order.id
                )
                group = await group_repo.create_for_order(
                    order, warehouse_id, geo_point_to_wkt(destination)
                )
                await reservation_repo.attach_to_group(order.id, group.id)
            pairs.append((group, order))

        vehicle_specs: list[VehicleSpec] = []
        for vehicle, depot in await vehicle_repo.get_routable_with_depot():
            if depot.location is None:
                continue
            depot_point = wkb_to_geo_point(depot.location)
            vehicle_specs.append(
                VehicleSpec(
                    id=str(vehicle.id),
                    depot=Location(
                        id=str(depot.id), lat=depot_point.lat, lng=depot_point.lng
                    ),
                    capacity_g=int(
                        round(float(vehicle.max_weight_kg) * GRAMS_PER_KG)
                    ),
                )
            )

        deliveries: list[Delivery] = []
        destination_of: dict[str, GeoPoint] = {}
        for group, order in pairs:
            key = str(group.id)
            destination = wkb_to_geo_point(order.delivery_location)
            destination_of[key] = destination
            deliveries.append(
                Delivery(
                    id=key,
                    lat=destination.lat,
                    lng=destination.lng,
                    demand_g=group_demand_g(order.items),
                )
            )

        result = solve_cvrp(
            vehicle_specs,
            deliveries,
            time_limit_seconds=time_limit_seconds,
            use_local_search=use_local_search,
        )

        pairs_by_key = {str(group.id): (group, order) for group, order in pairs}
        planned_routes: list[PlannedRouteRead] = []

        for planned in result.routes:
            vehicle_id = UUID(planned.vehicle_id)
            route = Route(vehicle_id=vehicle_id, status=ROUTE_PLANNED)
            session.add(route)
            await session.flush()

            group_ids: list[UUID] = []
            for sequence, stop_key in enumerate(planned.stop_ids, start=1):
                group, order = pairs_by_key[stop_key]
                session.add(
                    RouteStop(
                        route_id=route.id,
                        fulfillment_group_id=group.id,
                        sequence=sequence,
                        location=geo_point_to_wkt(destination_of[stop_key]),
                        status=ROUTE_STOP_PENDING,
                    )
                )
                group.assigned_route_id = route.id
                group.status = GROUP_ALLOCATED
                order.status = ORDER_ALLOCATED
                group_ids.append(group.id)

            write_outbox_event(
                session,
                aggregate_type=ROUTE_AGGREGATE,
                aggregate_id=route.id,
                event_type=ROUTE_PLANNED_EVENT,
                payload={
                    "route_id": str(route.id),
                    "vehicle_id": planned.vehicle_id,
                    "fulfillment_group_ids": [str(gid) for gid in group_ids],
                    "distance_m": planned.distance_m,
                },
            )

            planned_routes.append(
                PlannedRouteRead(
                    route_id=route.id,
                    vehicle_id=vehicle_id,
                    fulfillment_group_ids=group_ids,
                    distance_m=planned.distance_m,
                    travel_time_seconds=estimated_travel_time_seconds(
                        planned.distance_m
                    ),
                )
            )

        await session.commit()
    except HTTPException:
        await session.rollback()
        raise
    except Exception:
        await session.rollback()
        raise

    return BatchSolveResponse(
        solved=result.solved,
        routes=planned_routes,
        unassigned_fulfillment_group_ids=[
            UUID(key) for key in result.unassigned_ids
        ],
        skipped_orders_without_location=skipped_without_location,
        eligible_order_count=len(eligible_orders),
        operational_vehicle_count=len(vehicle_specs),
        total_distance_m=result.total_distance_m,
        total_travel_time_seconds=estimated_travel_time_seconds(
            result.total_distance_m
        ),
    )
