"""Fulfillment groups: the shipment unit routes are built from (FR-2, FR-7).

Phase 3 intake reserves inventory against an order. Phase 4 materialises one
group per order so route stops have a unit to reference, which is required
because ``route_stop.fulfillment_group_id`` is NOT NULL.
"""
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FulfillmentGroup, FulfillmentGroupItem, Order

PENDING_ALLOCATION = "PENDING_ALLOCATION"


class FulfillmentGroupRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_for_order(self, order_id: UUID) -> Optional[FulfillmentGroup]:
        """Return the order's open (unrouted) group, if one exists."""
        stmt = (
            select(FulfillmentGroup)
            .where(
                FulfillmentGroup.order_id == order_id,
                FulfillmentGroup.assigned_route_id.is_(None),
            )
            .order_by(FulfillmentGroup.created_at)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create_for_order(
        self,
        order: Order,
        warehouse_id: Optional[UUID],
        delivery_location_wkt: Optional[str],
    ) -> FulfillmentGroup:
        """Create a group carrying every item of the order.

        One group per order is the minimal interpretation of FR-2: splitting a
        single order across warehouses is the warehouse-selection heuristic
        (FR-15/FR-16), which is a separate component that v1 has not built.
        """
        group = FulfillmentGroup(
            order_id=order.id,
            warehouse_id=warehouse_id,
            status=PENDING_ALLOCATION,
            delivery_location=delivery_location_wkt,
            assigned_route_id=None,
        )
        self.session.add(group)
        await self.session.flush()

        for item in order.items:
            self.session.add(
                FulfillmentGroupItem(
                    fulfillment_group_id=group.id,
                    order_item_id=item.id,
                    quantity=item.quantity,
                )
            )
        await self.session.flush()
        return group
