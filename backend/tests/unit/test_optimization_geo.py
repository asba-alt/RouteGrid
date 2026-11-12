"""Straight-line distance and travel-time approximation (FR-29)."""
import pytest

from app.optimization.geo import haversine_m, travel_time_seconds


def test_zero_distance():
    assert haversine_m(17.3850, 78.4867, 17.3850, 78.4867) == pytest.approx(0.0)


def test_one_degree_of_latitude_is_about_111_km():
    distance = haversine_m(17.0, 78.0, 18.0, 78.0)
    assert distance == pytest.approx(111_195, rel=0.01)


def test_distance_is_symmetric():
    forward = haversine_m(17.3850, 78.4867, 17.4483, 78.3915)
    backward = haversine_m(17.4483, 78.3915, 17.3850, 78.4867)
    assert forward == pytest.approx(backward)


def test_travel_time_uses_the_speed_factor():
    # 1 km at 40 km/h is 90 seconds.
    assert travel_time_seconds(1_000, 40) == pytest.approx(90.0)


def test_travel_time_rejects_a_non_positive_speed():
    with pytest.raises(ValueError):
        travel_time_seconds(1_000, 0)
