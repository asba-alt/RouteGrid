from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AdvanceRequest(BaseModel):
    """Advance the simulation by a number of real seconds.

    ``route_id`` restricts the step to one route; otherwise every active route
    is advanced."""

    elapsed_seconds: float = Field(gt=0, le=86_400)
    route_id: Optional[UUID] = None


class VehiclePositionRead(BaseModel):
    route_id: UUID
    vehicle_id: Optional[UUID] = None
    lat: float
    lng: float
    simulated_at: datetime
    distance_travelled_m: int
    total_distance_m: int
    completed_stop_ids: list[UUID] = []
    remaining_stop_ids: list[UUID] = []
    finished: bool
    route_status: str
    # FR-35: telemetry must never be presented as real hardware data.
    simulated: bool = True


class AdvanceResponse(BaseModel):
    advanced: list[VehiclePositionRead] = []
    skipped_routes: int = 0
