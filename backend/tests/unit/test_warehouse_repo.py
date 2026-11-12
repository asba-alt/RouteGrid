"""Inventory reads used by order intake must be locking reads (FR-9).

This exercises the real repository method against a stub session so the emitted
SQL is inspected rather than mocked away. It proves the statement takes row
locks; it does not prove PostgreSQL concurrency behaviour, which needs a live
database.
"""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from app.repositories.warehouse_repo import WarehouseRepository


async def test_get_inventory_for_update_emits_for_update():
    session = MagicMock()
    captured = []

    async def fake_execute(statement, *args, **kwargs):
        captured.append(statement)
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        return result

    session.execute = AsyncMock(side_effect=fake_execute)
    repo = WarehouseRepository(session)

    await repo.get_inventory_for_update(uuid4(), ["A", "B"])

    assert session.execute.await_count == 1
    sql = str(captured[0].compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in sql
    assert "FROM inventory" in sql
    assert "warehouse_id" in sql
    assert "sku" in sql


async def test_get_inventory_for_update_is_scoped_to_one_warehouse_and_skus():
    session = MagicMock()
    captured = []

    async def fake_execute(statement, *args, **kwargs):
        captured.append(statement)
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        return result

    session.execute = AsyncMock(side_effect=fake_execute)
    repo = WarehouseRepository(session)

    await repo.get_inventory_for_update(uuid4(), ["A"])

    # A single bound parameter for the warehouse and the SKU list keeps the
    # lock scoped to exactly the rows the intake is about to reserve.
    compiled = captured[0].compile(dialect=postgresql.dialect())
    assert set(compiled.params) == {"warehouse_id_1", "sku_1"}


class _Row:
    def __init__(self, on_hand, reserved):
        self.on_hand = on_hand
        self.reserved = reserved


def _repo_returning(row):
    session = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = row
    session.execute = AsyncMock(return_value=result)
    session.flush = AsyncMock()
    return WarehouseRepository(session)


async def test_upsert_inventory_preserves_reserved_when_omitted():
    """Regression: correcting on-hand used to reset `reserved` to 0, silently
    destroying active holds. Verified against real PostgreSQL before the fix."""
    repo = _repo_returning(_Row(on_hand=10, reserved=4))

    updated = await repo.upsert_inventory(uuid4(), "SKU", on_hand=25)

    assert updated.on_hand == 25
    assert updated.reserved == 4, "holds must survive an on-hand correction"


async def test_upsert_inventory_can_still_set_reserved_explicitly():
    repo = _repo_returning(_Row(on_hand=10, reserved=4))

    updated = await repo.upsert_inventory(uuid4(), "SKU", on_hand=25, reserved=7)

    assert updated.reserved == 7

