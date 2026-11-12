"""Idempotency keys for order intake.

A client that retries ``POST /orders/intake`` with the same ``Idempotency-Key``
gets the original order back instead of creating a duplicate. The key row is
written in the same transaction as the order, so the guarantee holds even if the
process dies mid-request.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IdempotencyKey(Base):
    __tablename__ = "idempotency_key"

    key: Mapped[str] = mapped_column(primary_key=True)
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("order.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
