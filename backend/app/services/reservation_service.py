"""Releasing expired inventory holds (FR-12).

Holds created by order intake expire after ``RESERVATION_TTL_MINUTES``. Releasing
them must decrement the warehouse's ``reserved`` counter in the same transaction,
otherwise available stock stays understated forever.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Inventory, Reservation


async def release_expired(session: AsyncSession) -> int:
    """Delete holds past their expiry and give the stock back. Returns the count."""
    now = datetime.now(timezone.utc)
    expired = list(
        (
            await session.execute(
                select(Reservation).where(
                    Reservation.expires_at.is_not(None),
                    Reservation.expires_at < now,
                )
            )
        )
        .scalars()
        .all()
    )

    released = 0
    for reservation in expired:
        inventory = (
            await session.execute(
                select(Inventory).where(
                    Inventory.warehouse_id == reservation.warehouse_id,
                    Inventory.sku == reservation.sku,
                )
            )
        ).scalar_one_or_none()
        if inventory is not None:
            inventory.reserved = max(0, inventory.reserved - reservation.quantity)
        await session.delete(reservation)
        released += 1

    await session.commit()
    return released
