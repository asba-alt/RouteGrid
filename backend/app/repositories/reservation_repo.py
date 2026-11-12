from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Reservation


class ReservationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        warehouse_id: UUID,
        order_id: UUID,
        sku: str,
        quantity: int,
        expires_at: Optional[datetime] = None,
        fulfillment_group_id: Optional[UUID] = None,
    ) -> Reservation:
        reservation = Reservation(
            warehouse_id=warehouse_id,
            order_id=order_id,
            fulfillment_group_id=fulfillment_group_id,
            sku=sku,
            quantity=quantity,
            expires_at=expires_at,
        )
        self.session.add(reservation)
        await self.session.flush()
        return reservation

    async def get_warehouse_id_for_order(self, order_id: UUID) -> Optional[UUID]:
        stmt = (
            select(Reservation.warehouse_id)
            .where(Reservation.order_id == order_id)
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_order(self, order_id: UUID) -> list[Reservation]:
        stmt = (
            select(Reservation)
            .where(Reservation.order_id == order_id)
            .order_by(Reservation.sku)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def attach_to_group(self, order_id: UUID, group_id: UUID) -> int:
        """Point the order's still-unassigned holds at its fulfillment group.

        FR-11 describes a group reserving inventory, so the holds created at
        intake are linked here once the group exists."""
        stmt = (
            update(Reservation)
            .where(
                Reservation.order_id == order_id,
                Reservation.fulfillment_group_id.is_(None),
            )
            .values(fulfillment_group_id=group_id)
        )
        result = await self.session.execute(stmt)
        return result.rowcount
