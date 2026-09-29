"""Lightweight SQLAlchemy session factory helpers.

These helpers are a tiny scaffolding convenience and intentionally do not
wire environment variables at import time. Callers should provide the engine
object created by `engine.create_engine_from_url`.
"""
from contextlib import contextmanager
from sqlalchemy.orm import sessionmaker, Session


def make_session_factory(engine, *, expire_on_commit: bool = False):
    """Return a sessionmaker bound to the provided engine.

    Keep configuration minimal here so migration scripts and application code
    can import the factory without causing runtime side-effects.
    """
    return sessionmaker(bind=engine, expire_on_commit=expire_on_commit)


@contextmanager
def get_session(session_factory) -> Session:
    sess = session_factory()
    try:
        yield sess
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        sess.close()
