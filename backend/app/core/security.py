"""CSRF / Origin validation and brute-force throttling for session auth.

Cookie-based auth needs CSRF defence. This uses two layers:
- the session cookie is ``SameSite=Lax``, so cross-site POSTs do not carry it;
- state-changing requests must come from an allowed Origin (or Referer).
"""
import time
from urllib.parse import urlparse

from fastapi import HTTPException, Request, status

from app.core.config import settings

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}

# Simple in-memory login throttle: LOGIN_LIMIT attempts per LOGIN_WINDOW seconds.
LOGIN_LIMIT = 8
LOGIN_WINDOW_SECONDS = 300
_attempts: dict[str, list[float]] = {}


def _allowed_netlocs(request: Request) -> set[str]:
    """Hosts that count as same-origin for CSRF purposes.

    ``CORS_ORIGINS`` is authoritative when set (production). Behind a proxy the
    backend may see an internal Host, so the forwarded/host headers are also
    considered — browsers cannot spoof ``Origin``, which is what we compare.
    """
    netlocs = {urlparse(origin).netloc.lower() for origin in settings.cors_origins if origin}
    netlocs.add(request.url.netloc.lower())
    for header in ("x-forwarded-host", "host"):
        value = request.headers.get(header)
        if value:
            netlocs.add(value.split(",")[0].strip().lower())
    return {n for n in netlocs if n}


async def csrf_protect(request: Request) -> None:
    """Reject cross-origin state-changing requests when auth is enabled."""
    if not settings.auth_enabled or request.method.upper() in SAFE_METHODS:
        return

    source = request.headers.get("origin") or request.headers.get("referer")
    if not source:
        # Non-browser clients (curl, scripts) legitimately omit Origin. They
        # still need a valid session cookie, so this is not a bypass.
        return

    netloc = urlparse(source).netloc.lower()
    if netloc not in _allowed_netlocs(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-origin request rejected",
        )


def check_login_rate_limit(request: Request) -> None:
    key = (request.client.host if request.client else "unknown") or "unknown"
    now = time.monotonic()
    recent = [t for t in _attempts.get(key, []) if now - t < LOGIN_WINDOW_SECONDS]
    if len(recent) >= LOGIN_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again later.",
        )
    recent.append(now)
    _attempts[key] = recent


def reset_login_rate_limit(request: Request) -> None:
    key = (request.client.host if request.client else "unknown") or "unknown"
    _attempts.pop(key, None)
