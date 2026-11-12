"""CVRP solver behaviour (FR-20, FR-23, FR-26, FR-27).

Local search is disabled in these tests so results are deterministic; the
assertions are structural (capacity respected, everything served exactly once)
rather than pinning an exact stop order.
"""
from app.optimization.cvrp import Delivery, Location, VehicleSpec, solve_cvrp


def depot(id_="depot-1", lat=17.3850, lng=78.4867):
    return Location(id=id_, lat=lat, lng=lng)


def delivery(index, lat, lng, demand_g):
    return Delivery(id=f"g{index}", lat=lat, lng=lng, demand_g=demand_g)


def solved(vehicles, deliveries):
    return solve_cvrp(vehicles, deliveries, use_local_search=False)


def test_all_deliveries_served_when_capacity_allows():
    vehicles = [VehicleSpec(id="v1", depot=depot(), capacity_g=100_000)]
    deliveries = [
        delivery(i, 17.39 + i * 0.01, 78.49 + i * 0.01, 5_000) for i in range(1, 5)
    ]

    result = solved(vehicles, deliveries)

    assert result.solved is True
    assert result.unassigned_ids == []
    served = [sid for route in result.routes for sid in route.stop_ids]
    assert sorted(served) == sorted(d.id for d in deliveries)
    assert len(served) == len(set(served)), "a stop must not be visited twice"


def test_capacity_is_never_exceeded_and_excess_work_is_unassigned():
    vehicles = [VehicleSpec(id="v1", depot=depot(), capacity_g=100_000)]
    deliveries = [
        delivery(1, 17.39, 78.49, 60_000),
        delivery(2, 17.40, 78.50, 60_000),
    ]
    demand_of = {d.id: d.demand_g for d in deliveries}

    result = solved(vehicles, deliveries)

    for route in result.routes:
        assert sum(demand_of[sid] for sid in route.stop_ids) <= 100_000
    assert len(result.unassigned_ids) == 1
    assert len(result.routes) == 1
    assert len(result.routes[0].stop_ids) == 1


def test_delivery_exactly_at_capacity_is_served():
    vehicles = [VehicleSpec(id="v1", depot=depot(), capacity_g=50_000)]
    deliveries = [delivery(1, 17.39, 78.49, 50_000)]

    result = solved(vehicles, deliveries)

    assert result.unassigned_ids == []
    assert result.routes[0].stop_ids == ["g1"]


def test_delivery_heavier_than_any_vehicle_is_reported_unassigned():
    vehicles = [VehicleSpec(id="v1", depot=depot(), capacity_g=10_000)]
    deliveries = [delivery(1, 17.39, 78.49, 20_000)]

    result = solved(vehicles, deliveries)

    assert result.solved is True  # a legal solution exists: it simply serves nothing
    assert result.unassigned_ids == ["g1"]
    assert result.routes == []


def test_no_vehicles_reports_unsolved_with_everything_unassigned():
    result = solved([], [delivery(1, 17.39, 78.49, 1_000)])

    assert result.solved is False
    assert result.unassigned_ids == ["g1"]
    assert result.routes == []


def test_no_deliveries_is_solved_and_empty():
    result = solved([VehicleSpec(id="v1", depot=depot(), capacity_g=1_000)], [])

    assert result.solved is True
    assert result.routes == []
    assert result.unassigned_ids == []


def test_two_vehicles_split_work_when_one_cannot_carry_both():
    vehicles = [
        VehicleSpec(id="v1", depot=depot("d1"), capacity_g=60_000),
        VehicleSpec(id="v2", depot=depot("d2"), capacity_g=60_000),
    ]
    deliveries = [
        delivery(1, 17.39, 78.49, 60_000),
        delivery(2, 17.40, 78.50, 60_000),
    ]

    result = solved(vehicles, deliveries)

    assert result.unassigned_ids == []
    assert len(result.routes) == 2
    assert {route.vehicle_id for route in result.routes} == {"v1", "v2"}


def test_routes_contain_only_delivery_ids_never_depots():
    vehicles = [VehicleSpec(id="v1", depot=depot("depot-A"), capacity_g=100_000)]
    deliveries = [delivery(i, 17.39 + i * 0.01, 78.49, 1_000) for i in range(1, 4)]
    delivery_ids = {d.id for d in deliveries}

    result = solved(vehicles, deliveries)

    for route in result.routes:
        assert set(route.stop_ids) <= delivery_ids


def test_total_distance_is_the_sum_of_route_distances():
    vehicles = [VehicleSpec(id="v1", depot=depot(), capacity_g=100_000)]
    deliveries = [delivery(i, 17.39 + i * 0.01, 78.49 + i * 0.01, 1_000) for i in range(1, 4)]

    result = solved(vehicles, deliveries)

    assert result.total_distance_m == sum(r.distance_m for r in result.routes)
    assert result.total_distance_m > 0


def test_solve_is_deterministic_without_local_search():
    vehicles = [VehicleSpec(id="v1", depot=depot(), capacity_g=100_000)]
    deliveries = [delivery(i, 17.39 + i * 0.01, 78.49 + i * 0.01, 1_000) for i in range(1, 5)]

    first = solved(vehicles, deliveries)
    second = solved(vehicles, deliveries)

    assert [(r.vehicle_id, r.stop_ids, r.distance_m) for r in first.routes] == [
        (r.vehicle_id, r.stop_ids, r.distance_m) for r in second.routes
    ]
