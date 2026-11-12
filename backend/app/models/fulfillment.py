from typing import Optional
from uuid import UUID, uuid4

from geoalchemy2 import Geography
from geoalchemy2.elements import WKBElement
from sqlalchemy import CheckConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class FulfillmentGroup(Base, TimestampMixin):
    __tablename__ = "fulfillment_group"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("order.id", ondelete="CASCADE")
    )
    warehouse_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("warehouse.id"), nullable=True
    )
    status: Mapped[str]
    delivery_location: Mapped[Optional[WKBElement]] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=True
    )
    assigned_route_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("route.id"), nullable=True
    )


class FulfillmentGroupItem(Base):
    __tablename__ = "fulfillment_group_item"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    fulfillment_group_id: Mapped[UUID] = mapped_column(
        ForeignKey("fulfillment_group.id", ondelete="CASCADE")
    )
    order_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("order_item.id", ondelete="CASCADE")
    )
    quantity: Mapped[int] = mapped_column(CheckConstraint("quantity > 0"))
