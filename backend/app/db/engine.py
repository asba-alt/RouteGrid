"""Engine helper utilities for RouteGrid.

These helpers are intentionally minimal and dependency-free at import time. They
do not read environment variables directly; callers should pass a connection
URL string to `create_engine_from_url` to avoid hardcoding configuration names
in library code.

Do not implement migrations or models here; this file only provides a small
surface for creating SQLAlchemy engines that other modules or migration scripts
can consume.
"""
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def create_engine_from_url(url: str, *, echo: bool = False, future: bool = True) -> Engine:
    """Create and return a SQLAlchemy Engine bound to the given URL.

    Args:
        url: A SQLAlchemy-compatible database URL (e.g. "postgresql+psycopg2://user:pass@host/db").
        echo: If True, enable SQLAlchemy logging of emitted SQL for debugging.
        future: Enable SQLAlchemy 2.0 style features when supported.

    Returns:
        An instance of `sqlalchemy.engine.Engine`.
    """
    # NOTE: callers should handle installation of DB drivers and provide a
    # connection string appropriate for their environment. This helper keeps the
    # responsibility of configuration outside library code.
    return create_engine(url, echo=echo, future=future)
