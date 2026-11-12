from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from geoalchemy2 import Geography
from geoalchemy2.elements import WKBElement
from sqlalchemy import CheckConstraint, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin


class Order(Base, TimestampMixin):
    __tablename__ = "order"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    customer_id: Mapped[Optional[UUID]] = mapped_column(nullable=True)
    # Human-facing identity so operators never work with bare UUIDs.
    customer_name: Mapped[Optional[str]] = mapped_column(nullable=True)
    reference: Mapped[Optional[str]] = mapped_column(nullable=True, index=True)
    status: Mapped[str]
    delivery_location: Mapped[Optional[WKBElement]] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=True
    )
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_item"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("order.id", ondelete="CASCADE")
    )
    sku: Mapped[str]
    quantity: Mapped[int] = mapped_column(CheckConstraint("quantity > 0"))
    weight_kg: Mapped[Decimal] = mapped_column(
        Numeric, CheckConstraint("weight_kg >= 0")
    )

    order: Mapped["Order"] = relationship(back_populates="items")
