"""Offset pagination shared by the list endpoints."""
from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel

T = TypeVar("T")

MAX_LIMIT = 200


class PageParams:
    """Dependency: ``?limit=&offset=`` with sane bounds."""

    def __init__(
        self,
        limit: int = Query(default=50, ge=1, le=MAX_LIMIT, description="Max rows"),
        offset: int = Query(default=0, ge=0, description="Rows to skip"),
    ) -> None:
        self.limit = limit
        self.offset = offset


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
