"""Transactional outbox writing (requirements.md FR-45).

Outbox rows are staged on the caller's session and are only durable when the
caller commits. This keeps the event write in the same transaction as the
business state change, which is the whole point of the outbox pattern.
"""
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OutboxEvent


def write_outbox_event(
    session: AsyncSession,
    *,
    aggregate_type: str,
    aggregate_id: UUID,
    event_type: str,
    payload: dict[str, Any],
    metadata: Optional[dict[str, Any]] = None,
) -> OutboxEvent:
    event = OutboxEvent(
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_type=event_type,
        payload=payload,
        published=False,
        metadata_=metadata,
    )
    session.add(event)
    return event
