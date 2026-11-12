from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.disruption import DISRUPTION_KINDS


class DisruptionCreate(BaseModel):
    kind: str = Field(description=f"One of: {', '.join(DISRUPTION_KINDS)}")
    route_id: Optional[UUID] = None
    vehicle_id: Optional[UUID] = None
    description: Optional[str] = None
    # Break the vehicle out of service (default for a breakdown).
    take_vehicle_out_of_service: Optional[bool] = None


class DisruptionResolve(BaseModel):
    resolution: Optional[str] = None
    reoptimize: bool = False


class DisruptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: str
    status: str
    vehicle_id: Optional[UUID] = None
    route_id: Optional[UUID] = None
    description: Optional[str] = None
    affected_group_ids: Optional[dict] = None
    resolution: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None


class DisruptionImpact(BaseModel):
    disruption: DisruptionRead
    released_group_ids: list[UUID] = []
    preserved_completed_stop_ids: list[UUID] = []
    route_status: Optional[str] = None
    vehicle_operational: Optional[bool] = None
    reoptimized_routes: int = 0
    reoptimized_reason: Optional[str] = None
