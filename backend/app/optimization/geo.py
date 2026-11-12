"""Distance and travel-time approximation (requirements.md FR-29).

RouteGrid v1 explicitly does not use road-network routing. Travel time is
straight-line distance divided by a configurable speed factor, and that
approximation is labelled as such rather than presented as an accurate ETA.
"""
from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two points in metres."""
    phi1, phi2 = radians(lat1), radians(lat2)
    delta_phi = phi2 - phi1
    delta_lambda = radians(lng2 - lng1)
    a = (
        sin(delta_phi / 2) ** 2
        + cos(phi1) * cos(phi2) * sin(delta_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * asin(sqrt(min(1.0, a)))


def travel_time_seconds(distance_m: float, speed_kmh: float) -> float:
    """Approximate travel time for a straight-line distance (FR-29)."""
    if speed_kmh <= 0:
        raise ValueError("speed_kmh must be positive")
    return distance_m / 1000.0 / speed_kmh * 3600.0
