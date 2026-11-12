from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.db.session import get_db
from app.schemas.optimization import BatchSolveRequest, BatchSolveResponse
from app.services import optimization_service

router = APIRouter(prefix="/api/v1/optimization", tags=["optimization"])


@router.post("/solve", response_model=BatchSolveResponse)
async def solve_batch(
    payload: Optional[BatchSolveRequest] = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> BatchSolveResponse:
    """Run one batch optimization pass.

    Pending orders are assigned to operational vehicles and sequenced together.
    Deliveries that cannot be served are returned as unassigned instead of
    failing the whole batch.
    """
    options = payload or BatchSolveRequest()
    return await optimization_service.solve_batch(
        db,
        time_limit_seconds=options.time_limit_seconds,
        use_local_search=options.use_local_search,
    )
