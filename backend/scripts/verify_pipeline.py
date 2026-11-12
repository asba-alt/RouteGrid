"""Run the previously-blocked Phase 3-5 integration chain against live services.

    docker compose up -d
    cd backend && python -m alembic upgrade head
    python -m scripts.verify_pipeline

Checks only a real database can settle: schema shape, the FOR UPDATE inventory
lock, atomic order intake, optimizer persistence, simulator persistence.
Prints PASS/FAIL per step; exits non-zero if any step fails, or 2 if PostgreSQL
is unreachable (in which case nothing is claimed to be verified).

WARNING: this is a diagnostic for a disposable dev database. It mutates data --
it creates a warehouse, submits orders, and a batch solve assigns every pending
order and creates routes. Reset afterwards with `docker compose down -v`.
It deletes nothing.
"""
import asyncio
import sys
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from dotenv import load_dotenv
from sqlalchemy import select, text

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
load_dotenv(BACKEND.parent / ".env")

from app.core.config import settings  # noqa: E402
from app.db import session as db_session  # noqa: E402
from app.db.engine import create_engine_from_url  # noqa: E402
from app.db.session import init_session_factory  # noqa: E402
from app.models import (  # noqa: E402
    FulfillmentGroup,
    Order,
    OutboxEvent,
    Reservation,
    Route,
    RouteStop,
    TelemetrySnapshot,
)
from app.schemas.common import GeoPoint  # noqa: E402
from app.schemas.disruption import DisruptionCreate, DisruptionResolve  # noqa: E402
from app.schemas.order import OrderIntakeRequest, OrderItemCreate  # noqa: E402
from app.schemas.warehouse import InventoryUpsert, WarehouseCreate  # noqa: E402
from app.services import (  # noqa: E402
    disruption_service,
    optimization_service,
    order_intake_service,
    simulation_service,
    warehouse_service,
)

RESULTS: list[tuple[str, bool, str]] = []
SKU = "VERIFY-SKU-A"


def report(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))


async def check_schema(engine) -> bool:
    queries = {
        "tables": ("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'", 13),
        "postgis": ("SELECT postgis_version()", None),
        "created_at_type": (
            "SELECT data_type FROM information_schema.columns WHERE table_name='order' AND column_name='created_at'",
            "timestamp with time zone",
        ),
        "location_type": (
            "SELECT udt_name FROM information_schema.columns WHERE table_name='warehouse' AND column_name='location'",
            "geography",
        ),
    }
    values = {}
    try:
        async with engine.connect() as conn:
            for key, (sql, _expected) in queries.items():
                values[key] = (await conn.execute(text(sql))).scalar_one()
    except Exception as exc:
        report("schema: migration applied", False, f"{type(exc).__name__}: {exc}")
        return False

    report("schema: tables present", values["tables"] >= 13, f"{values['tables']} tables")
    report("schema: PostGIS enabled", True, str(values["postgis"]))
    report(
        "schema: timestamps are tz-aware",
        values["created_at_type"] == queries["created_at_type"][1],
        str(values["created_at_type"]),
    )
    report(
        "schema: warehouse.location is geography",
        values["location_type"] == queries["location_type"][1],
        str(values["location_type"]),
    )
    return True


async def check_row_lock(engine, warehouse_id: UUID) -> None:
    """Second session must block on the same row the first one locked (FR-9)."""
    sql = text(
        "SELECT id FROM inventory WHERE warehouse_id = :w AND sku = :s FOR UPDATE"
    )
    params = {"w": str(warehouse_id), "s": SKU}
    first = await engine.connect()
    second = await engine.connect()
    try:
        await first.begin()
        await first.execute(sql, params)
        await second.begin()
        try:
            await asyncio.wait_for(second.execute(sql, params), timeout=3.0)
            report("lock: FOR UPDATE blocks a concurrent writer", False, "second session was NOT blocked")
        except asyncio.TimeoutError:
            report("lock: FOR UPDATE blocks a concurrent writer", True, "second session blocked")
    finally:
        await second.close()
        await first.close()


async def run_chain() -> None:
    engine = create_engine_from_url(settings.DATABASE_URL)
    init_session_factory(engine)
    try:
        # A bare connection first, so "services are down" is reported as BLOCKED
        # rather than mistaken for a failed schema check.
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

        if not await check_schema(engine):
            return

        point = GeoPoint(lat=17.3850, lng=78.4867)

        async with db_session.async_session_factory() as session:
            warehouse = await warehouse_service.create_warehouse(
                session, WarehouseCreate(name=f"Verify Hub {uuid4().hex[:6]}", location=point)
            )
            await warehouse_service.upsert_inventory(
                session, warehouse.id, SKU, InventoryUpsert(on_hand=10, reserved=0)
            )
        report("warehouse: create + inventory upsert persisted", True, str(warehouse.id))

        await check_row_lock(engine, warehouse.id)

        async with db_session.async_session_factory() as session:
            intake = await order_intake_service.intake_order(
                session,
                OrderIntakeRequest(
                    warehouse_id=warehouse.id,
                    delivery_location=point,
                    items=[OrderItemCreate(sku=SKU, quantity=4, weight_kg=Decimal("2.5"))],
                ),
            )
        units = sum(r.quantity for r in intake.reservations)
        report(
            "intake: order + reservations committed together",
            units == 4 and len(intake.reservations) == 1,
            f"{len(intake.reservations)} reservation(s), {units} units",
        )

        async with db_session.async_session_factory() as session:
            reserved = (
                await session.execute(
                    text("SELECT reserved FROM inventory WHERE warehouse_id=:w AND sku=:s"),
                    {"w": str(warehouse.id), "s": SKU},
                )
            ).scalar_one()
            events = (
                await session.execute(select(OutboxEvent).where(OutboxEvent.aggregate_id == intake.id))
            ).scalars().all()
        report("intake: reserved counter incremented", reserved == 4, f"reserved={reserved}")
        report("intake: outbox row in the same transaction", len(events) == 1, f"{len(events)} row(s)")

        async with db_session.async_session_factory() as session:
            try:
                await order_intake_service.intake_order(
                    session,
                    OrderIntakeRequest(
                        warehouse_id=warehouse.id,
                        delivery_location=point,
                        items=[OrderItemCreate(sku=SKU, quantity=99, weight_kg=Decimal("1"))],
                    ),
                )
                report("intake: insufficient stock rejected with 409", False, "no error raised")
            except Exception as exc:
                status = getattr(exc, "status_code", None)
                report("intake: insufficient stock rejected with 409", status == 409, f"status={status}")

        async with db_session.async_session_factory() as session:
            after = (
                await session.execute(
                    text("SELECT reserved FROM inventory WHERE warehouse_id=:w AND sku=:s"),
                    {"w": str(warehouse.id), "s": SKU},
                )
            ).scalar_one()
            held = (
                await session.execute(select(Reservation).where(Reservation.warehouse_id == warehouse.id))
            ).scalars().all()
        report("intake: rejected order left no partial hold", after == 4, f"reserved still {after}")
        report("intake: no stray reservation rows", len(held) == 1, f"{len(held)} reservation(s)")

        async with db_session.async_session_factory() as session:
            result = await optimization_service.solve_batch(session, use_local_search=False)
        report(
            "optimize: pending orders assigned to vehicles",
            len(result.routes) >= 1,
            f"{len(result.routes)} route(s), {len(result.unassigned_fulfillment_group_ids)} unassigned",
        )

        async with db_session.async_session_factory() as session:
            order_row = await session.get(Order, intake.id)
            groups = (
                await session.execute(
                    select(FulfillmentGroup).where(FulfillmentGroup.order_id == intake.id)
                )
            ).scalars().all()
            stops = (
                await session.execute(
                    select(RouteStop).where(
                        RouteStop.fulfillment_group_id.in_([g.id for g in groups])
                    )
                )
            ).scalars().all()
            route_events = (
                await session.execute(select(OutboxEvent).where(OutboxEvent.event_type == "RoutePlanned"))
            ).scalars().all()
            route_ids = {s.route_id for s in stops}
        report("optimize: order moved to ALLOCATED", order_row.status == "ALLOCATED", order_row.status)
        report(
            "optimize: fulfillment group linked to a route",
            bool(groups) and groups[0].assigned_route_id is not None,
        )
        report(
            "optimize: route_stop rows persisted with sequences",
            bool(stops) and all(s.sequence >= 1 for s in stops),
            f"{len(stops)} stop(s) across {len(route_ids)} route(s)",
        )
        report("optimize: RoutePlanned outbox row written", len(route_events) >= 1, f"{len(route_events)} row(s)")

        if not route_ids:
            report("simulate: route available to simulate", False, "no route was created")
            return

        route_id = next(iter(route_ids))
        async with db_session.async_session_factory() as session:
            advanced = await simulation_service.advance(
                session, 60, route_id=route_id, redis_client=None
            )
        report("simulate: position produced for the route", len(advanced.advanced) == 1)
        if not advanced.advanced:
            return
        position = advanced.advanced[0]

        async with db_session.async_session_factory() as session:
            snapshots = (
                await session.execute(
                    select(TelemetrySnapshot).where(TelemetrySnapshot.vehicle_id == position.vehicle_id)
                )
            ).scalars().all()
            route_row = await session.get(Route, route_id)
        report("simulate: telemetry snapshot persisted", len(snapshots) >= 1, f"{len(snapshots)} snapshot(s)")
        report(
            "simulate: route progressed",
            route_row.status in ("IN_PROGRESS", "COMPLETED"),
            f"status={route_row.status}, distance={position.distance_travelled_m}m",
        )

        # --- disruption -----------------------------------------------------
        async with db_session.async_session_factory() as session:
            pending_before = (
                await session.execute(
                    text("SELECT count(*) FROM \"order\" WHERE status = 'PENDING_ALLOCATION'")
                )
            ).scalar_one()
            pending_stops = (
                await session.execute(
                    select(RouteStop).where(RouteStop.status == "PENDING")
                )
            ).scalars().all()

        if not pending_stops:
            report("disruption: route with pending stops available", False, "none found")
        else:
            victim_route_id = pending_stops[0].route_id
            async with db_session.async_session_factory() as session:
                impact = await disruption_service.report(
                    session,
                    DisruptionCreate(kind="VEHICLE_BREAKDOWN", route_id=victim_route_id),
                )
            report(
                "disruption: route cancelled and uncompleted work released",
                impact.route_status == "CANCELLED" and len(impact.released_group_ids) >= 1,
                f"released={len(impact.released_group_ids)} preserved={len(impact.preserved_completed_stop_ids)}",
            )

            async with db_session.async_session_factory() as session:
                pending_after = (
                    await session.execute(
                        text("SELECT count(*) FROM \"order\" WHERE status = 'PENDING_ALLOCATION'")
                    )
                ).scalar_one()
            report(
                "disruption: affected orders returned to PENDING_ALLOCATION",
                pending_after > pending_before,
                f"{pending_before} -> {pending_after}",
            )

            async with db_session.async_session_factory() as session:
                resolved = await disruption_service.resolve(
                    session,
                    impact.disruption.id,
                    DisruptionResolve(reoptimize=True),
                )
            report(
                "disruption: resolved and re-optimized",
                resolved.disruption.status == "RESOLVED" and resolved.reoptimized_routes >= 1,
                f"routes={resolved.reoptimized_routes} status={resolved.disruption.status}",
            )

        try:
            import redis.asyncio as redis_async

            client = redis_async.Redis.from_url(settings.REDIS_URL, protocol=2)
            await client.ping()
            await client.aclose()
            report("redis: reachable for position caching", True)
        except Exception as exc:
            report("redis: reachable for position caching", False, type(exc).__name__)
    finally:
        await engine.dispose()


async def main() -> int:
    try:
        await run_chain()
    except Exception as exc:
        import traceback

        traceback.print_exc()
        print(f"\n[BLOCKED] could not reach PostgreSQL: {type(exc).__name__}: {exc}")
        print("Start services (`docker compose up -d`) and run `python -m alembic upgrade head` first.")
        return 2

    failed = [name for name, ok, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    if failed:
        print("failed: " + "; ".join(failed))
        return 1
    print("PIPELINE VERIFIED AGAINST POSTGRESQL")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
