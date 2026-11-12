from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class RouteStopRead(BaseModel):
    id: UUID
    sequence: int
    status: str
    fulfillment_group_id: UUID
    lat: Optional[float] = None
    lng: Optional[float] = None
    arrived_at: Optional[datetime] = None


class RouteRead(BaseModel):
    id: UUID
    vehicle_id: Optional[UUID] = None
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    stops: list[RouteStopRead] = []
