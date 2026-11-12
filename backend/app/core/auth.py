"""Session-cookie authentication (replaces the shared API key).

The browser never receives a secret. It gets an opaque, HttpOnly session cookie
set by the backend; the server resolves it through Redis (or the in-memory
fallback) to identify the operator.

Password verification supports either a PBKDF2 hash (preferred, generated with
``python -m scripts.make_password_hash``) or, in development only, a plaintext
``OPERATOR_PASSWORD``.
"""
import hashlib
import secrets
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, Request, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.session import read_session

SESSION_COOKIE = "rg_session"
DEV_USER_ID = UUID("00000000-0000-0000-0000-000000000001")

_HASH_ALGORITHM = "pbkdf2_sha256"
_HASH_ITERATIONS = 260_000


class CurrentUser(BaseModel):
    id: UUID = Field(default=DEV_USER_ID)
    name: str
    role: str


def hash_password(password: str, *, iterations: int = _HASH_ITERATIONS) -> str:
    """Produce ``pbkdf2_sha256$iterations$salt$hash`` for OPERATOR_PASSWORD_HASH."""
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"{_HASH_ALGORITHM}${iterations}${salt.hex()}${derived.hex()}"


def verify_password(password: str) -> bool:
    spec = settings.OPERATOR_PASSWORD_HASH.strip()
    if spec:
        try:
            algorithm, iterations, salt_hex, hash_hex = spec.split("$")
            if algorithm != _HASH_ALGORITHM:
                return False
            derived = hashlib.pbkdf2_hmac(
                "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
            )
            return secrets.compare_digest(derived.hex(), hash_hex)
        except (ValueError, TypeError):
            return False
    if settings.OPERATOR_PASSWORD:
        return secrets.compare_digest(password, settings.OPERATOR_PASSWORD)
    return False


def verify_username(username: str) -> bool:
    return secrets.compare_digest(username, settings.OPERATOR_USERNAME)


def _unauthorized(detail: str = "Authentication required") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Session"},
    )


async def get_current_user(request: Request) -> CurrentUser:
    # Development mode: no operator credentials configured, so the app is open.
    if not settings.auth_enabled:
        return CurrentUser(id=DEV_USER_ID, name="Dev Operator", role="dispatcher")

    session_id = request.cookies.get(SESSION_COOKIE)
    if not session_id:
        raise _unauthorized()

    data: Optional[dict] = await read_session(session_id)
    if not data:
        raise _unauthorized("Session expired or invalid")

    return CurrentUser(
        id=UUID(data["id"]), name=data["name"], role=data.get("role", "dispatcher")
    )
