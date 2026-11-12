from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Order, OrderItem
from app.schemas.order import OrderItemCreate


class OrderRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        customer_id: Optional[UUID],
        status: str,
        delivery_location_wkt: Optional[str],
        items_data: list[OrderItemCreate],
        customer_name: Optional[str] = None,
        reference: Optional[str] = None,
    ) -> Order:
        order = Order(
            customer_id=customer_id,
            customer_name=customer_name,
            reference=reference,
            status=status,
            delivery_location=delivery_location_wkt,
        )
        for item in items_data:
            order.items.append(
                OrderItem(
                    sku=item.sku,
                    quantity=item.quantity,
                    weight_kg=item.weight_kg,
                )
            )
        self.session.add(order)
        await self.session.flush()
        return order

    async def get_all(self, status: Optional[str] = None) -> list[Order]:
        stmt = select(Order).order_by(Order.created_at.desc())
        if status is not None:
            stmt = stmt.where(Order.status == status)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_status_with_items(self, status: str) -> list[Order]:
        """Orders in a given lifecycle state with their items eagerly loaded.

        The optimizer uses this to find work awaiting allocation."""
        stmt = (
            select(Order)
            .where(Order.status == status)
            .options(selectinload(Order.items))
            .order_by(Order.created_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, id: UUID) -> Optional[Order]:
        stmt = (
            select(Order)
            .where(Order.id == id)
            .options(selectinload(Order.items))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(self, order: Order, status: str) -> Order:
        order.status = status
        await self.session.flush()
        return order

    async def count(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(Order))
        return result.scalar_one()
