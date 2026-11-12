from uuid import UUID, uuid4

from geoalchemy2 import Geography
from geoalchemy2.elements import WKBElement
from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Warehouse(Base):
    __tablename__ = "warehouse"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str]
    location: Mapped[WKBElement] = mapped_column(
        Geography(geometry_type="POINT", srid=4326)
    )
    operational: Mapped[bool] = mapped_column(default=True)

    inventory: Mapped[list["Inventory"]] = relationship(
        back_populates="warehouse", cascade="all, delete-orphan"
    )


class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    warehouse_id: Mapped[UUID] = mapped_column(
        ForeignKey("warehouse.id", ondelete="CASCADE")
    )
    sku: Mapped[str]
    on_hand: Mapped[int] = mapped_column(
        CheckConstraint("on_hand >= 0"), default=0
    )
    reserved: Mapped[int] = mapped_column(
        CheckConstraint("reserved >= 0"), default=0
    )

    warehouse: Mapped["Warehouse"] = relationship(back_populates="inventory")

    __table_args__ = (UniqueConstraint("warehouse_id", "sku"),)
