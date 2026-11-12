"""Server-side session storage.

Sessions live in Redis when it is reachable, with an in-memory fallback so a
Redis outage degrades the cache rather than locking operators out. Session ids
are opaque random tokens; they never carry user data themselves.
"""
import json
import secrets
from typing import Optional

from app.core import redis as redis_module

# Fallback store for when Redis is unavailable. Process-local: sessions do not
# survive a restart, which is acceptable for a single-instance demo.
_memory: dict[str, dict] = {}


def _key(session_id: str) -> str:
    return f"session:{session_id}"


async def create_session(data: dict, ttl_minutes: int) -> str:
    session_id = secrets.token_urlsafe(32)
    client = redis_module.redis_client
    if client is not None:
        try:
            await client.set(_key(session_id), json.dumps(data), ex=ttl_minutes * 60)
            return session_id
        except Exception:
            pass  # fall through to memory
    _memory[session_id] = data
    return session_id


async def read_session(session_id: str) -> Optional[dict]:
    if not session_id:
        return None
    client = redis_module.redis_client
    if client is not None:
        try:
            raw = await client.get(_key(session_id))
            if raw:
                return json.loads(raw)
        except Exception:
            pass
    return _memory.get(session_id)


async def delete_session(session_id: str) -> None:
    client = redis_module.redis_client
    if client is not None:
        try:
            await client.delete(_key(session_id))
        except Exception:
            pass
    _memory.pop(session_id, None)
