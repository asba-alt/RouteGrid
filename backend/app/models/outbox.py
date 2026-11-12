from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base


class OutboxEvent(Base):
    __tablename__ = "outbox_event"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    aggregate_type: Mapped[str]
    aggregate_id: Mapped[UUID]
    event_type: Mapped[str]
    payload: Mapped[dict] = mapped_column(JSON)
    published: Mapped[bool] = mapped_column(default=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSON, nullable=True
    )

    __table_args__ = (
        Index("idx_outbox_published", "published", "occurred_at"),
    )
