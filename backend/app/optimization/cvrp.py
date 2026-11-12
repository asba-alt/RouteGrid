"""Capacitated vehicle routing problem (CVRP) over a batch of deliveries.

FR-23/FR-27: vehicle assignment and stop sequencing are decided together in one
solve rather than order-by-order. FR-26: no time windows in v1. FR-20: each
vehicle's weight capacity is a hard constraint. FR-29: arc cost is straight-line
distance, which is proportional to travel time at a constant speed factor.

Deliveries are allowed to be dropped via a disjunction penalty so an infeasible
or capacity-constrained batch reports unassigned work explicitly instead of
failing or silently overloading a vehicle.
"""
from dataclasses import dataclass, field
from typing import Optional, Sequence

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from app.optimization.geo import haversine_m


@dataclass(frozen=True)
class Location:
    id: str
    lat: float
    lng: float


@dataclass(frozen=True)
class VehicleSpec:
    id: str
    depot: Location
    capacity_g: int


@dataclass(frozen=True)
class Delivery:
    id: str
    lat: float
    lng: float
    demand_g: int


@dataclass
class PlannedRoute:
    vehicle_id: str
    stop_ids: list[str]
    distance_m: int


@dataclass
class SolveResult:
    routes: list[PlannedRoute] = field(default_factory=list)
    unassigned_ids: list[str] = field(default_factory=list)
    total_distance_m: int = 0
    solved: bool = False


def _build_node_layout(
    vehicles: Sequence[VehicleSpec], deliveries: Sequence[Delivery]
) -> tuple[list[Location], dict[str, int], int]:
    """Return (nodes, depot_id -> node index, delivery_node_offset).

    Depots are deduplicated so several vehicles sharing a warehouse share one
    graph node."""
    depot_index: dict[str, int] = {}
    nodes: list[Location] = []
    for vehicle in vehicles:
        if vehicle.depot.id not in depot_index:
            depot_index[vehicle.depot.id] = len(nodes)
            nodes.append(vehicle.depot)
    delivery_offset = len(nodes)
    nodes.extend(Location(d.id, d.lat, d.lng) for d in deliveries)
    return nodes, depot_index, delivery_offset


def solve_cvrp(
    vehicles: Sequence[VehicleSpec],
    deliveries: Sequence[Delivery],
    *,
    time_limit_seconds: int = 5,
    use_local_search: bool = True,
    drop_penalty_g: Optional[int] = None,
) -> SolveResult:
    if not deliveries:
        return SolveResult(routes=[], unassigned_ids=[], solved=True)
    if not vehicles:
        return SolveResult(
            routes=[],
            unassigned_ids=[delivery.id for delivery in deliveries],
            solved=False,
        )

    nodes, depot_index, delivery_offset = _build_node_layout(vehicles, deliveries)
    num_nodes = len(nodes)
    num_vehicles = len(vehicles)
    starts = [depot_index[vehicle.depot.id] for vehicle in vehicles]

    demand_of_node = [0] * num_nodes
    for position, delivery in enumerate(deliveries):
        demand_of_node[delivery_offset + position] = delivery.demand_g

    manager = pywrapcp.RoutingIndexManager(
        num_nodes, num_vehicles, starts, list(starts)
    )
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index: int, to_index: int) -> int:
        origin = nodes[manager.IndexToNode(from_index)]
        target = nodes[manager.IndexToNode(to_index)]
        return int(round(haversine_m(origin.lat, origin.lng, target.lat, target.lng)))

    transit_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_index)

    def demand_callback(from_index: int) -> int:
        return demand_of_node[manager.IndexToNode(from_index)]

    demand_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_index,
        0,
        [vehicle.capacity_g for vehicle in vehicles],
        True,
        "Capacity",
    )

    # Allow a delivery to be dropped, at a cost high enough that the solver only
    # does so when no vehicle can legally carry it.
    penalty = (
        drop_penalty_g
        if drop_penalty_g is not None
        else max((d.demand_g for d in deliveries), default=0)
        + sum((d.demand_g for d in deliveries), 0)
        + 1_000_000
    )
    for position in range(len(deliveries)):
        routing.AddDisjunction(
            [manager.NodeToIndex(delivery_offset + position)], penalty
        )

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    if use_local_search:
        search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        search_parameters.time_limit.FromSeconds(time_limit_seconds)

    assignment = routing.SolveWithParameters(search_parameters)
    if assignment is None:
        return SolveResult(
            routes=[],
            unassigned_ids=[delivery.id for delivery in deliveries],
            solved=False,
        )

    routes: list[PlannedRoute] = []
    served: set[str] = set()
    total_distance_m = 0

    for vehicle_position, vehicle in enumerate(vehicles):
        index = routing.Start(vehicle_position)
        stop_ids: list[str] = []
        route_distance_m = 0
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node >= delivery_offset:
                delivery = deliveries[node - delivery_offset]
                stop_ids.append(delivery.id)
                served.add(delivery.id)
            previous = index
            index = assignment.Value(routing.NextVar(index))
            route_distance_m += routing.GetArcCostForVehicle(
                previous, index, vehicle_position
            )
        total_distance_m += route_distance_m
        if stop_ids:
            routes.append(
                PlannedRoute(
                    vehicle_id=vehicle.id,
                    stop_ids=stop_ids,
                    distance_m=route_distance_m,
                )
            )

    unassigned_ids = [
        delivery.id for delivery in deliveries if delivery.id not in served
    ]
    return SolveResult(
        routes=routes,
        unassigned_ids=unassigned_ids,
        total_distance_m=total_distance_m,
        solved=True,
    )
