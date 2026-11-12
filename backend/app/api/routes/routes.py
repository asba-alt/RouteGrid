from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.pagination import PageParams
from app.core.auth import CurrentUser, get_current_user
from app.db.session import get_db
from app.schemas.route import RouteRead
from app.services import route_service

router = APIRouter(prefix="/api/v1/routes", tags=["routes"])


@router.get("", response_model=list[RouteRead])
async def list_routes(
    response: Response,
    status: Optional[str] = None,
    page: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[RouteRead]:
    routes, total = await route_service.list_routes(
        db, status, limit=page.limit, offset=page.offset
    )
    response.headers["X-Total-Count"] = str(total)
    return routes


@router.get("/{route_id}", response_model=RouteRead)
async def get_route(
    route_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> RouteRead:
    return await route_service.get_route(db, route_id)
