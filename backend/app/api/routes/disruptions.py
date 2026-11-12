from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.pagination import PageParams
from app.core.auth import CurrentUser, get_current_user
from app.db.session import get_db
from app.schemas.disruption import (
    DisruptionCreate,
    DisruptionImpact,
    DisruptionRead,
    DisruptionResolve,
)
from app.services import disruption_service

router = APIRouter(prefix="/api/v1/disruptions", tags=["disruptions"])


@router.post("", response_model=DisruptionImpact, status_code=http_status.HTTP_201_CREATED)
async def report_disruption(
    payload: DisruptionCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> DisruptionImpact:
    """Report a disruption. Uncompleted deliveries are released back to the
    allocation pool; completed deliveries are preserved."""
    return await disruption_service.report(db, payload)


@router.get("", response_model=list[DisruptionRead])
async def list_disruptions(
    response: Response,
    status: Optional[str] = None,
    page: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[DisruptionRead]:
    items, total = await disruption_service.list_disruptions(
        db, status, limit=page.limit, offset=page.offset
    )
    response.headers["X-Total-Count"] = str(total)
    return items


@router.get("/{disruption_id}", response_model=DisruptionRead)
async def get_disruption(
    disruption_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> DisruptionRead:
    return await disruption_service.get_disruption(db, disruption_id)


@router.post("/{disruption_id}/resolve", response_model=DisruptionImpact)
async def resolve_disruption(
    disruption_id: UUID,
    payload: DisruptionResolve,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> DisruptionImpact:
    """Resolve a disruption, optionally re-running batch optimization."""
    return await disruption_service.resolve(db, disruption_id, payload)
