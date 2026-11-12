"""Vehicle movement along an assigned route (FR-32, FR-33).

Position is a pure function of elapsed time: no randomness and no wall clock.
Given the same waypoints and elapsed seconds, the result is always identical,
which is what makes the simulator reproducible in tests.

Time compression: ``time_compression_ratio`` seconds of simulated time pass per
second of caller-supplied elapsed time (default 60, so one real second is one
simulated minute). Distance covered follows FR-29's approximation:
distance = simulated_time x speed factor.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Sequence

from app.optimization.geo import haversine_m

DEPOT_START_KEY = "DEPOT_START"
DEPOT_END_KEY = "DEPOT_END"


@dataclass(frozen=True)
class Waypoint:
    """A point the vehicle drives through, in order."""

    key: str
    lat: float
    lng: float
    is_stop: bool = True


@dataclass
class Progress:
    lat: float
    lng: float
    distance_travelled_m: float
    total_distance_m: float
    completed_keys: list[str] = field(default_factory=list)
    remaining_keys: list[str] = field(default_factory=list)
    finished: bool = False
    simulated_at: Optional[datetime] = None


def simulated_elapsed_seconds(
    real_elapsed_seconds: float, time_compression_ratio: int
) -> float:
    return max(0.0, real_elapsed_seconds) * max(1, time_compression_ratio)


def distance_covered_m(
    real_elapsed_seconds: float, time_compression_ratio: int, speed_kmh: float
) -> float:
    seconds = simulated_elapsed_seconds(real_elapsed_seconds, time_compression_ratio)
    return seconds / 3600.0 * speed_kmh * 1000.0


def cumulative_distances(waypoints: Sequence[Waypoint]) -> list[float]:
    """Distance from the route start to each waypoint."""
    distances = [0.0]
    for origin, target in zip(waypoints, waypoints[1:]):
        distances.append(
            distances[-1]
            + haversine_m(origin.lat, origin.lng, target.lat, target.lng)
        )
    return distances


def total_distance_m(waypoints: Sequence[Waypoint]) -> float:
    return cumulative_distances(waypoints)[-1] if waypoints else 0.0


def advance(
    waypoints: Sequence[Waypoint],
    elapsed_seconds: float,
    *,
    speed_kmh: float,
    time_compression_ratio: int,
    started_at: Optional[datetime] = None,
) -> Progress:
    if not waypoints:
        raise ValueError("waypoints must not be empty")

    cumulative = cumulative_distances(waypoints)
    total = cumulative[-1]
    travelled = min(
        distance_covered_m(elapsed_seconds, time_compression_ratio, speed_kmh),
        total,
    )

    if total <= 0:
        lat, lng = waypoints[0].lat, waypoints[0].lng
        finished = True
    elif travelled >= total:
        lat, lng = waypoints[-1].lat, waypoints[-1].lng
        finished = True
    else:
        leg = 0
        for index in range(len(waypoints) - 1):
            if cumulative[index] <= travelled < cumulative[index + 1]:
                leg = index
                break
        leg_length = cumulative[leg + 1] - cumulative[leg]
        ratio = 0.0 if leg_length == 0 else (travelled - cumulative[leg]) / leg_length
        origin, target = waypoints[leg], waypoints[leg + 1]
        lat = origin.lat + (target.lat - origin.lat) * ratio
        lng = origin.lng + (target.lng - origin.lng) * ratio
        finished = False

    # Nothing is complete before the vehicle has moved at all.
    completed: list[str] = []
    if travelled > 0:
        completed = [
            waypoint.key
            for position, waypoint in enumerate(waypoints)
            if waypoint.is_stop and cumulative[position] <= travelled
        ]
    remaining = [
        waypoint.key
        for waypoint in waypoints
        if waypoint.is_stop and waypoint.key not in completed
    ]

    simulated_at = None
    if started_at is not None:
        simulated_at = started_at + timedelta(
            seconds=simulated_elapsed_seconds(elapsed_seconds, time_compression_ratio)
        )

    return Progress(
        lat=lat,
        lng=lng,
        distance_travelled_m=travelled,
        total_distance_m=total,
        completed_keys=completed,
        remaining_keys=remaining,
        finished=finished,
        simulated_at=simulated_at,
    )
