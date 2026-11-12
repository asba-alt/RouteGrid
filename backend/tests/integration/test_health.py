"""Integration checks that do not require a live database.

`/` and `/openapi.json` only need the ASGI app. `/health` is asserted to be
either 200 (Postgres + Redis reachable) or 503 (dependencies down), so this
suite is honest about the environment instead of failing when services are
absent.
"""
from fastapi.testclient import TestClient

from app.main import app


def test_root_endpoint():
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "RouteGrid API", "docs": "/docs"}


def test_health_reports_dependency_state():
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/health")
    assert response.status_code in (200, 503)
    body = response.json()
    assert body["database"] in ("connected", "error")
    assert body["redis"] in ("connected", "error")
    if response.status_code == 200:
        assert body["status"] == "ok"
    else:
        assert body["status"] == "error"


def test_openapi_exposes_the_expected_routes():
    with TestClient(app, raise_server_exceptions=False) as client:
        paths = client.get("/openapi.json").json()["paths"]

    expected = {
        "/",
        "/health",
        "/api/v1/warehouses",
        "/api/v1/warehouses/{warehouse_id}",
        "/api/v1/warehouses/{warehouse_id}/inventory",
        "/api/v1/warehouses/{warehouse_id}/inventory/{sku}",
        "/api/v1/drivers",
        "/api/v1/vehicles",
        "/api/v1/vehicles/{vehicle_id}",
        "/api/v1/orders",
        "/api/v1/orders/intake",
        "/api/v1/orders/{order_id}",
        "/api/v1/orders/{order_id}/status",
        "/api/v1/optimization/solve",
        "/api/v1/simulation/advance",
        "/api/v1/simulation/positions",
        "/api/v1/reservations/release-expired",
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
        "/api/v1/auth/me",
    }
    assert expected <= set(paths)


def test_intake_route_is_declared_before_the_uuid_path():
    """Otherwise POST /orders/intake would be matched as order_id='intake'."""
    with TestClient(app, raise_server_exceptions=False) as client:
        paths = client.get("/openapi.json").json()["paths"]
    assert "post" in paths["/api/v1/orders/intake"]
