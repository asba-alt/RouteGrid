"""Movement model for the GPS simulator (FR-32, FR-33, FR-29).

Everything here is pure, so these tests need no database and no clock.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.optimization.geo import haversine_m
from app.simulation.movement import (
    DEPOT_END_KEY,
    DEPOT_START_KEY,
    Waypoint,
    advance,
    cumulative_distances,
    distance_covered_m,
    simulated_elapsed_seconds,
    total_distance_m,
)

SPEED_KMH = 40
RATIO = 60
START = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)


def route_waypoints():
    return [
        Waypoint(key=DEPOT_START_KEY, lat=0.0, lng=0.0, is_stop=False),
        Waypoint(key="s1", lat=0.0, lng=0.01),
        Waypoint(key="s2", lat=0.0, lng=0.02),
        Waypoint(key="s3", lat=0.0, lng=0.03),
        Waypoint(key=DEPOT_END_KEY, lat=0.0, lng=0.0, is_stop=False),
    ]


def elapsed_for(distance_m):
    """Elapsed real seconds needed to cover ``distance_m``."""
    return distance_m / 1000 / SPEED_KMH * 3600 / RATIO


def step(waypoints, elapsed):
    return advance(
        waypoints,
        elapsed,
        speed_kmh=SPEED_KMH,
        time_compression_ratio=RATIO,
        started_at=START,
    )


def test_no_movement_before_time_elapses():
    progress = step(route_waypoints(), 0)

    assert progress.lat == 0.0
    assert progress.lng == 0.0
    assert progress.distance_travelled_m == 0
    assert progress.completed_keys == []
    assert progress.finished is False
    assert progress.simulated_at == START


def test_time_compression_scales_simulated_time():
    assert simulated_elapsed_seconds(1, 60) == 60
    assert simulated_elapsed_seconds(1, 1) == 1
    assert simulated_elapsed_seconds(-5, 60) == 0


def test_distance_covered_uses_the_speed_factor():
    # 60 simulated seconds at 40 km/h is 666.67 m.
    assert distance_covered_m(1, 60, 40) == pytest.approx(666.666, rel=1e-4)


def test_position_is_interpolated_along_the_first_leg():
    waypoints = route_waypoints()
    half_leg = haversine_m(0.0, 0.0, 0.0, 0.01) / 2

    progress = step(waypoints, elapsed_for(half_leg))

    assert progress.lng == pytest.approx(0.005, rel=1e-3)
    assert progress.lat == pytest.approx(0.0)
    assert progress.distance_travelled_m == pytest.approx(half_leg, rel=1e-3)


def test_stops_complete_in_sequence_as_they_are_passed():
    waypoints = route_waypoints()
    cumulative = cumulative_distances(waypoints)

    progress = step(waypoints, elapsed_for(cumulative[2] + 1))

    assert progress.completed_keys == ["s1", "s2"]
    assert progress.remaining_keys == ["s3"]


def test_depot_waypoints_are_never_reported_as_stops():
    waypoints = route_waypoints()

    progress = step(waypoints, elapsed_for(total_distance_m(waypoints) * 0.5))

    assert DEPOT_START_KEY not in progress.completed_keys
    assert DEPOT_END_KEY not in progress.completed_keys
    assert DEPOT_START_KEY not in progress.remaining_keys
    assert DEPOT_END_KEY not in progress.remaining_keys


def test_route_completes_at_the_final_depot():
    waypoints = route_waypoints()
    total = total_distance_m(waypoints)

    progress = step(waypoints, elapsed_for(total))

    assert progress.finished is True
    assert progress.distance_travelled_m == pytest.approx(total)
    assert progress.completed_keys == ["s1", "s2", "s3"]
    assert progress.remaining_keys == []
    assert (progress.lat, progress.lng) == (0.0, 0.0)


def test_overshooting_clamps_to_route_completion():
    waypoints = route_waypoints()

    progress = step(waypoints, elapsed_for(total_distance_m(waypoints)) * 100)

    assert progress.finished is True
    assert progress.distance_travelled_m == pytest.approx(total_distance_m(waypoints))
    assert progress.completed_keys == ["s1", "s2", "s3"]


def test_simulated_timestamp_advances_with_compressed_time():
    progress = step(route_waypoints(), 30)

    assert progress.simulated_at == START + timedelta(seconds=30 * RATIO)


def test_identical_inputs_produce_identical_output():
    waypoints = route_waypoints()
    elapsed = elapsed_for(total_distance_m(waypoints) * 0.42)

    first, second = step(waypoints, elapsed), step(waypoints, elapsed)

    assert (first.lat, first.lng, first.completed_keys) == (
        second.lat,
        second.lng,
        second.completed_keys,
    )


def test_single_waypoint_route_is_immediately_finished():
    progress = step([Waypoint(key="s1", lat=17.0, lng=78.0)], 10)

    assert progress.finished is True
    assert progress.total_distance_m == 0
    assert progress.completed_keys == []
    assert progress.remaining_keys == ["s1"]


def test_empty_waypoints_is_rejected():
    with pytest.raises(ValueError):
        step([], 10)
