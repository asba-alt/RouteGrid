from uuid import UUID

from pydantic import BaseModel, Field

from app.core.config import settings


class BatchSolveRequest(BaseModel):
    """Optional tuning for a single optimization pass.

    ``time_limit_seconds`` bounds the solver when local search is enabled; with
    ``use_local_search=False`` only the deterministic construction solution is
    used. The default comes from ``OPTIMIZER_TIME_LIMIT_SECONDS`` so the budget
    can be tuned per environment without a code change."""

    time_limit_seconds: int = Field(
        default=settings.OPTIMIZER_TIME_LIMIT_SECONDS, ge=1, le=60
    )
    use_local_search: bool = True


class PlannedRouteRead(BaseModel):
    route_id: UUID
    vehicle_id: UUID
    fulfillment_group_ids: list[UUID] = []
    distance_m: int = 0
    travel_time_seconds: int = 0


class BatchSolveResponse(BaseModel):
    solved: bool
    routes: list[PlannedRouteRead] = []
    unassigned_fulfillment_group_ids: list[UUID] = []
    skipped_orders_without_location: int = 0
    eligible_order_count: int = 0
    operational_vehicle_count: int = 0
    total_distance_m: int = 0
    total_travel_time_seconds: int = 0
