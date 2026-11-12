from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Inventory, Warehouse


class WarehouseRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self, name: str, location_wkt: str, operational: bool
    ) -> Warehouse:
        warehouse = Warehouse(
            name=name, location=location_wkt, operational=operational
        )
        self.session.add(warehouse)
        await self.session.flush()
        return warehouse

    async def get_all(self, operational: Optional[bool] = None) -> list[Warehouse]:
        stmt = select(Warehouse).order_by(Warehouse.name)
        if operational is not None:
            stmt = stmt.where(Warehouse.operational == operational)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, id: UUID) -> Optional[Warehouse]:
        stmt = (
            select(Warehouse)
            .where(Warehouse.id == id)
            .options(selectinload(Warehouse.inventory))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(self, warehouse: Warehouse, **kwargs) -> Warehouse:
        for key, value in kwargs.items():
            setattr(warehouse, key, value)
        await self.session.flush()
        return warehouse

    async def get_inventory(self, warehouse_id: UUID) -> list[Inventory]:
        stmt = (
            select(Inventory)
            .where(Inventory.warehouse_id == warehouse_id)
            .order_by(Inventory.sku)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_inventory_for_update(
        self, warehouse_id: UUID, skus: Sequence[str]
    ) -> list[Inventory]:
        """Lock the inventory rows for these SKUs so concurrent order intake
        cannot oversell the same stock (FR-9). Rows must be locked before the
        availability check and held until the transaction commits."""
        stmt = (
            select(Inventory)
            .where(
                Inventory.warehouse_id == warehouse_id,
                Inventory.sku.in_(list(skus)),
            )
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_inventory(
        self,
        warehouse_id: UUID,
        sku: str,
        on_hand: int,
        reserved: Optional[int] = None,
    ) -> Inventory:
        stmt = select(Inventory).where(
            Inventory.warehouse_id == warehouse_id, Inventory.sku == sku
        )
        result = await self.session.execute(stmt)
        inventory = result.scalar_one_or_none()
        if inventory is None:
            inventory = Inventory(
                warehouse_id=warehouse_id,
                sku=sku,
                on_hand=on_hand,
                reserved=reserved or 0,
            )
            self.session.add(inventory)
        else:
            inventory.on_hand = on_hand
            # Only touch holds when explicitly supplied, so correcting a stock
            # count cannot destroy in-flight reservations.
            if reserved is not None:
                inventory.reserved = reserved
        await self.session.flush()
        return inventory

    async def count(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(Warehouse))
        return result.scalar_one()
