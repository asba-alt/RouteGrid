from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Driver(Base):
    __tablename__ = "driver"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[Optional[str]] = mapped_column(nullable=True)


class Vehicle(Base):
    __tablename__ = "vehicle"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    external_id: Mapped[Optional[str]] = mapped_column(nullable=True)
    driver_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("driver.id"), nullable=True
    )
    depot_warehouse_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("warehouse.id"), nullable=True
    )
    max_weight_kg: Mapped[Decimal] = mapped_column(Numeric)
    operational: Mapped[bool] = mapped_column(default=True)

    driver: Mapped[Optional["Driver"]] = relationship()
