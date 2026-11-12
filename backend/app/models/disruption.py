"""Disruption records (Phase 6).

A disruption is an auditable operational event: a vehicle breakdown, a delay, an
unavailable vehicle or a failed delivery. Resolving the disruption is what
releases affected work back to the allocation queue, so the history of what was
affected and how it was handled is preserved rather than overwritten.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin

DISRUPTION_KINDS = (
    "VEHICLE_BREAKDOWN",
    "TRAFFIC_DELAY",
    "VEHICLE_UNAVAILABLE",
    "DELIVERY_FAILURE",
    "OTHER",
)

DISRUPTION_OPEN = "OPEN"
DISRUPTION_RESOLVED = "RESOLVED"
DISRUPTION_UNRESOLVED = "UNRESOLVED"


class Disruption(Base, TimestampMixin):
    __tablename__ = "disruption"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    kind: Mapped[str]
    status: Mapped[str] = mapped_column(default=DISRUPTION_OPEN)
    vehicle_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("vehicle.id"), nullable=True
    )
    route_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("route.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[Optional[str]] = mapped_column(nullable=True)
    # Fulfillment groups that were released back to the pending pool.
    affected_group_ids: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    resolution: Mapped[Optional[str]] = mapped_column(nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (Index("idx_disruption_status", "status", "created_at"),)
