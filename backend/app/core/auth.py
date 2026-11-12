"""Authentication seam (NFR-4).

Real JWT/RBAC is still deferred, but the seam now enforces a shared API key
when ``API_KEY`` is configured:

- ``API_KEY`` unset → development mode, every request is allowed (documented).
- ``API_KEY`` set   → every endpoint requires a matching ``X-API-Key`` header.

The comparison is constant-time so a wrong key cannot be discovered by timing.
"""
import secrets
from uuid import UUID

from fastapi import HTTPException, Request, status
from pydantic import BaseModel, Field

from app.core.config import settings

DEV_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
API_KEY_HEADER = "X-API-Key"


class CurrentUser(BaseModel):
    id: UUID = Field(default=DEV_USER_ID)
    name: str
    role: str


async def get_current_user(request: Request) -> CurrentUser:
    expected = settings.API_KEY
    if expected:
        provided = request.headers.get(API_KEY_HEADER, "")
        if not provided or not secrets.compare_digest(provided, expected):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid API key",
                headers={"WWW-Authenticate": "ApiKey"},
            )
    return CurrentUser(id=DEV_USER_ID, name="Dev Operator", role="dispatcher")
