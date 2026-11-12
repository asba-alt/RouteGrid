from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.db.session import get_db
from app.services import reservation_service

router = APIRouter(prefix="/api/v1/reservations", tags=["reservations"])


@router.post("/release-expired")
async def release_expired_reservations(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Release holds that passed their expiry, returning stock to availability.

    Intended to be called on a schedule; safe to call repeatedly.
    """
    released = await reservation_service.release_expired(db)
    return {"released": released}
