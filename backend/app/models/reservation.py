from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Reservation(Base, TimestampMixin):
    __tablename__ = "reservation"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    warehouse_id: Mapped[UUID] = mapped_column(
        ForeignKey("warehouse.id", ondelete="CASCADE")
    )
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("order.id", ondelete="CASCADE")
    )
    fulfillment_group_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("fulfillment_group.id", ondelete="CASCADE"), nullable=True
    )
    sku: Mapped[str]
    quantity: Mapped[int] = mapped_column(CheckConstraint("quantity > 0"))
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
