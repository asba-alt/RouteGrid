"""Seed data shape and determinism (Phase 2 requirement 5)."""
import re

from scripts import seed_data

POINT_RE = re.compile(r"POINT\(([-\d.]+) ([-\d.]+)\)")


def parse_point(wkt):
    match = POINT_RE.search(wkt)
    assert match, f"not a POINT WKT: {wkt}"
    lng, lat = (float(v) for v in match.groups())
    return lng, lat


def test_seed_counts_match_the_demo_scale():
    assert len(seed_data.WAREHOUSES) == 5
    assert len(seed_data.SKUS) == 40
    assert len(seed_data.DRIVER_NAMES) == 25
    assert len(seed_data.ORDER_POINTS) == seed_data.ORDER_COUNT == 10


def test_skus_are_unique():
    assert len(set(seed_data.SKUS)) == len(seed_data.SKUS)


def test_vehicle_tiers_are_the_five_configured_weights():
    assert seed_data.VEHICLE_TIERS_KG == [500, 750, 1000, 1250, 1500]


def test_coordinates_are_longitude_first():
    """A swapped pair would put Hyderabad's latitude in the longitude slot."""
    for _, wkt in seed_data.WAREHOUSES:
        lng, lat = parse_point(wkt)
        assert 78.0 < lng < 79.0, wkt
        assert 17.0 < lat < 18.0, wkt

    for wkt in seed_data.ORDER_POINTS:
        lng, lat = parse_point(wkt)
        assert 78.0 < lng < 79.0, wkt
        assert 17.0 < lat < 18.0, wkt


def test_all_wkts_declare_srid_4326():
    wkts = [wkt for _, wkt in seed_data.WAREHOUSES] + seed_data.ORDER_POINTS
    assert all(wkt.startswith("SRID=4326;POINT(") for wkt in wkts)


def test_customer_ids_are_deterministic_and_distinct():
    assert seed_data.customer_id_for(3) == seed_data.customer_id_for(3)
    assert seed_data.customer_id_for(3) != seed_data.customer_id_for(4)
