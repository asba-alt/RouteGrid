"""Read models for routes (used by the operations dashboard)."""
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.route_repo import RouteRepository
from app.schemas.common import wkb_to_geo_point
from app.schemas.route import RouteRead, RouteStopRead


def _to_read(route) -> RouteRead:
    stops = []
    for stop in sorted(route.stops, key=lambda item: item.sequence):
        lat = lng = None
        if stop.location is not None:
            try:
                point = wkb_to_geo_point(stop.location)
                lat, lng = point.lat, point.lng
            except Exception:
                # A stop with an unreadable coordinate is still reported, just
                # without geometry, so the rest of the route stays usable.
                lat = lng = None
        stops.append(
            RouteStopRead(
                id=stop.id,
                sequence=stop.sequence,
                status=stop.status,
                fulfillment_group_id=stop.fulfillment_group_id,
                lat=lat,
                lng=lng,
                arrived_at=stop.arrived_at,
            )
        )
    return RouteRead(
        id=route.id,
        vehicle_id=route.vehicle_id,
        status=route.status,
        created_at=route.created_at,
        started_at=route.started_at,
        completed_at=route.completed_at,
        stops=stops,
    )


async def list_routes(
    session: AsyncSession,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[RouteRead], int]:
    repo = RouteRepository(session)
    routes = await repo.get_all_with_stops(status=status, limit=limit, offset=offset)
    total = await repo.count(status=status)
    return [_to_read(route) for route in routes], total


async def get_route(session: AsyncSession, route_id: UUID) -> RouteRead:
    repo = RouteRepository(session)
    route = await repo.get_by_id_with_stops(route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="Route not found")
    return _to_read(route)
