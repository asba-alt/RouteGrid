from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from geoalchemy2 import Geography
from geoalchemy2.elements import WKBElement
from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Route(Base, TimestampMixin):
    __tablename__ = "route"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    vehicle_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("vehicle.id"), nullable=True
    )
    status: Mapped[str]
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    stops: Mapped[list["RouteStop"]] = relationship(
        back_populates="route",
        cascade="all, delete-orphan",
        order_by="RouteStop.sequence",
    )


class RouteStop(Base):
    __tablename__ = "route_stop"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    route_id: Mapped[UUID] = mapped_column(
        ForeignKey("route.id", ondelete="CASCADE")
    )
    fulfillment_group_id: Mapped[UUID] = mapped_column(
        ForeignKey("fulfillment_group.id")
    )
    sequence: Mapped[int]
    location: Mapped[Optional[WKBElement]] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=True
    )
    status: Mapped[str] = mapped_column(default="PENDING")
    arrived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    route: Mapped["Route"] = relationship(back_populates="stops")

    __table_args__ = (UniqueConstraint("route_id", "sequence"),)
