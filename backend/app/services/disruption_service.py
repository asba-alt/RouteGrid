"""Disruption handling (Phase 6).

Guarantees:
- completed deliveries are never released or reopened;
- released work goes back to ``PENDING_ALLOCATION`` so the next batch can pick it
  up, and the route keeps an audit trail of what was released;
- a failed re-optimization never loses the disruption record: it is marked
  ``UNRESOLVED`` so an operator can intervene manually.
"""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.events.outbox import write_outbox_event
from app.models import FulfillmentGroup, Order, Vehicle
from app.models.disruption import (
    DISRUPTION_KINDS,
    DISRUPTION_OPEN,
    DISRUPTION_RESOLVED,
    DISRUPTION_UNRESOLVED,
)
from app.repositories.disruption_repo import DisruptionRepository
from app.repositories.route_repo import (
    ROUTE_CANCELLED,
    ROUTE_COMPLETED,
    ROUTE_STOP_COMPLETED,
    ROUTE_STOP_RELEASED,
)
from app.schemas.disruption import (
    DisruptionCreate,
    DisruptionImpact,
    DisruptionRead,
    DisruptionResolve,
)
from app.services import optimization_service
from app.services.order_service import PENDING_ALLOCATION

TERMINAL_ORDER_STATUSES = {"DELIVERED", "CANCELLED", "FAILED"}
SERVICE_ENDING_KINDS = {"VEHICLE_BREAKDOWN", "VEHICLE_UNAVAILABLE"}

DISRUPTION_AGGREGATE = "disruption"
DISRUPTION_EVENT = "DisruptionReported"


def _read(disruption) -> DisruptionRead:
    return DisruptionRead.model_validate(disruption)


async def report(
    session: AsyncSession, data: DisruptionCreate
) -> DisruptionImpact:
    if data.kind not in DISRUPTION_KINDS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown disruption kind. Expected one of: {', '.join(DISRUPTION_KINDS)}",
        )

    repo = DisruptionRepository(session)
    try:
        route = None
        if data.route_id is not None:
            route = await repo.get_route_with_stops(data.route_id)
            if route is None:
                raise HTTPException(status_code=404, detail="Route not found")
            if route.status == ROUTE_COMPLETED:
                raise HTTPException(
                    status_code=409,
                    detail="Route is already completed and cannot be disrupted",
                )
            if route.status == ROUTE_CANCELLED:
                raise HTTPException(
                    status_code=409, detail="Route is already cancelled"
                )

        vehicle_id = data.vehicle_id or (route.vehicle_id if route is not None else None)
        if vehicle_id is None and route is None:
            raise HTTPException(
                status_code=422,
                detail="Provide route_id or vehicle_id",
            )

        released: list[UUID] = []
        preserved: list[UUID] = []

        if route is not None:
            for stop in route.stops:
                # Completed deliveries are never reopened.
                if stop.status == ROUTE_STOP_COMPLETED:
                    preserved.append(stop.id)
                    continue

                group = await session.get(FulfillmentGroup, stop.fulfillment_group_id)
                if group is not None:
                    group.assigned_route_id = None
                    group.status = PENDING_ALLOCATION
                    if group.order_id is not None:
                        order = await session.get(Order, group.order_id)
                        if order is not None and order.status not in TERMINAL_ORDER_STATUSES:
                            order.status = PENDING_ALLOCATION
                    released.append(group.id)
                stop.status = ROUTE_STOP_RELEASED
            route.status = ROUTE_CANCELLED

        take_out_of_service = data.take_vehicle_out_of_service
        if take_out_of_service is None:
            take_out_of_service = data.kind in SERVICE_ENDING_KINDS

        vehicle_operational: Optional[bool] = None
        if vehicle_id is not None:
            vehicle = await session.get(Vehicle, vehicle_id)
            if vehicle is None:
                raise HTTPException(status_code=404, detail="Vehicle not found")
            if take_out_of_service:
                vehicle.operational = False
            vehicle_operational = vehicle.operational

        disruption = await repo.create(
            kind=data.kind,
            status=DISRUPTION_OPEN,
            vehicle_id=vehicle_id,
            route_id=route.id if route is not None else None,
            description=data.description,
            affected_group_ids={"group_ids": [str(g) for g in released]},
        )

        write_outbox_event(
            session,
            aggregate_type=DISRUPTION_AGGREGATE,
            aggregate_id=disruption.id,
            event_type=DISRUPTION_EVENT,
            payload={
                "disruption_id": str(disruption.id),
                "kind": data.kind,
                "route_id": str(route.id) if route is not None else None,
                "released_group_ids": [str(g) for g in released],
                "preserved_stop_ids": [str(s) for s in preserved],
            },
        )

        await session.commit()
    except HTTPException:
        await session.rollback()
        raise
    except Exception:
        await session.rollback()
        raise

    return DisruptionImpact(
        disruption=_read(disruption),
        released_group_ids=released,
        preserved_completed_stop_ids=preserved,
        route_status=route.status if route is not None else None,
        vehicle_operational=vehicle_operational,
    )


async def resolve(
    session: AsyncSession, disruption_id: UUID, data: DisruptionResolve
) -> DisruptionImpact:
    repo = DisruptionRepository(session)
    disruption = await repo.get_by_id(disruption_id)
    if disruption is None:
        raise HTTPException(status_code=404, detail="Disruption not found")
    if disruption.status == DISRUPTION_RESOLVED:
        raise HTTPException(status_code=409, detail="Disruption is already resolved")

    disruption.status = DISRUPTION_RESOLVED
    disruption.resolution = data.resolution
    disruption.resolved_at = datetime.now(timezone.utc)

    reoptimized = 0
    reason: Optional[str] = None
    if data.reoptimize:
        try:
            # solve_batch commits, so the disruption update and the new routes
            # land in the same transaction.
            result = await optimization_service.solve_batch(
                session, use_local_search=False
            )
            reoptimized = len(result.routes)
            unassigned = len(result.unassigned_fulfillment_group_ids)
            if unassigned:
                reason = f"{unassigned} deliveries could not be assigned"
        except Exception:
            # Keep the failure visible instead of pretending recovery worked.
            await session.rollback()
            disruption = await repo.get_by_id(disruption_id)
            if disruption is not None:
                disruption.status = DISRUPTION_UNRESOLVED
                disruption.resolution = (
                    (data.resolution or "Recovery failed")
                    + " [re-optimization failed; manual intervention required]"
                )
                await session.commit()
            raise HTTPException(
                status_code=503,
                detail="Re-optimization failed; disruption marked UNRESOLVED for manual intervention",
            )
    else:
        await session.commit()

    refreshed = await repo.get_by_id(disruption_id)
    return DisruptionImpact(
        disruption=_read(refreshed or disruption),
        reoptimized_routes=reoptimized,
        reoptimized_reason=reason,
    )


async def list_disruptions(
    session: AsyncSession,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[DisruptionRead], int]:
    repo = DisruptionRepository(session)
    rows = await repo.get_all(status=status, limit=limit, offset=offset)
    total = await repo.count(status=status)
    return [_read(row) for row in rows], total


async def get_disruption(session: AsyncSession, disruption_id: UUID) -> DisruptionRead:
    repo = DisruptionRepository(session)
    disruption = await repo.get_by_id(disruption_id)
    if disruption is None:
        raise HTTPException(status_code=404, detail="Disruption not found")
    return _read(disruption)
