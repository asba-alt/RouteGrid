"""Request/response schema validation."""
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.common import GeoPoint, wkb_to_geo_point
from app.schemas.order import (
    OrderCreate,
    OrderIntakeRequest,
    OrderItemCreate,
)
from app.schemas.warehouse import InventoryUpsert, WarehouseUpdate
from app.services.warehouse_service import geo_point_to_wkt


def test_wkt_is_longitude_first():
    assert geo_point_to_wkt(GeoPoint(lat=17.385, lng=78.4867)) == (
        "SRID=4326;POINT(78.4867 17.385)"
    )


def test_wkb_round_trip():
    from geoalchemy2 import Geography
    from sqlalchemy.dialects import postgresql
    from shapely import wkb as shapely_wkb
    from shapely.geometry import Point

    processor = Geography(geometry_type="POINT", srid=4326).result_processor(
        postgresql.dialect(), None
    )
    element = processor(shapely_wkb.dumps(Point(78.4867, 17.385)))
    point = wkb_to_geo_point(element)
    assert point.lat == pytest.approx(17.385)
    assert point.lng == pytest.approx(78.4867)


def test_wkb_to_geo_point_accepts_ewkt_string():
    """Regression: with expire_on_commit=False an ORM attribute still holds the
    WKT literal that was assigned, not a WKBElement. Verified against real
    PostgreSQL, where this crashed order intake."""
    point = wkb_to_geo_point("SRID=4326;POINT(78.4867 17.385)")
    assert point.lat == pytest.approx(17.385)
    assert point.lng == pytest.approx(78.4867)


def test_wkb_to_geo_point_accepts_plain_wkt_string():
    point = wkb_to_geo_point("POINT(78.4867 17.385)")
    assert point.lat == pytest.approx(17.385)
    assert point.lng == pytest.approx(78.4867)


def test_wkb_to_geo_point_accepts_hex_wkb_string():
    import binascii

    from shapely import wkb as shapely_wkb
    from shapely.geometry import Point

    hexed = binascii.hexlify(shapely_wkb.dumps(Point(78.4867, 17.385))).decode()
    point = wkb_to_geo_point(hexed)
    assert point.lat == pytest.approx(17.385)
    assert point.lng == pytest.approx(78.4867)


@pytest.mark.parametrize("quantity", [0, -1])
def test_order_item_quantity_must_be_positive(quantity):
    with pytest.raises(ValidationError):
        OrderItemCreate(sku="A", quantity=quantity, weight_kg=Decimal("1"))


def test_order_item_weight_cannot_be_negative():
    with pytest.raises(ValidationError):
        OrderItemCreate(sku="A", quantity=1, weight_kg=Decimal("-0.01"))


def test_order_requires_at_least_one_item():
    with pytest.raises(ValidationError):
        OrderCreate(items=[])


def test_intake_requires_a_warehouse():
    with pytest.raises(ValidationError):
        OrderIntakeRequest(
            items=[OrderItemCreate(sku="A", quantity=1, weight_kg=Decimal("1"))]
        )


def test_intake_accepts_minimal_payload():
    warehouse_id = uuid4()
    request = OrderIntakeRequest(
        warehouse_id=warehouse_id,
        items=[OrderItemCreate(sku="A", quantity=2, weight_kg=Decimal("1.5"))],
    )
    assert request.warehouse_id == warehouse_id
    assert request.delivery_location is None


def test_inventory_upsert_rejects_negative_values():
    with pytest.raises(ValidationError):
        InventoryUpsert(on_hand=-1)
    with pytest.raises(ValidationError):
        InventoryUpsert(on_hand=1, reserved=-1)


def test_inventory_upsert_reserved_defaults_to_unset_not_zero():
    """Absent `reserved` must mean "leave holds alone", never "zero them"."""
    assert InventoryUpsert(on_hand=5).reserved is None
    assert InventoryUpsert(on_hand=5, reserved=2).reserved == 2


def test_patch_models_only_report_supplied_fields():
    assert WarehouseUpdate(name="Renamed").model_dump(exclude_unset=True) == {
        "name": "Renamed"
    }
    assert WarehouseUpdate().model_dump(exclude_unset=True) == {}
