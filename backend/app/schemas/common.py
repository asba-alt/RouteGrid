from typing import Any

from pydantic import BaseModel
from shapely import wkb as shapely_wkb


class GeoPoint(BaseModel):
    lat: float
    lng: float


class ErrorDetail(BaseModel):
    detail: str


def _ewkt_to_geo_point(text: str) -> GeoPoint:
    """Parse 'SRID=4326;POINT(lng lat)' / 'POINT(lng lat)' (longitude first)."""
    body = text.split(";")[-1]
    inside = body[body.index("(") + 1 : body.index(")")]
    lng, lat = (float(part) for part in inside.split()[:2])
    return GeoPoint(lat=lat, lng=lng)


def wkb_to_geo_point(element: Any) -> GeoPoint:
    """Convert a PostGIS value into a GeoPoint.

    Accepts every shape this can arrive in:
    - ``WKBElement`` (normal database read) whose ``.data`` is WKB bytes;
    - a hex WKB string (WKBElement built from text);
    - an EWKT/WKT string, which is what an ORM attribute still holds when a
      row was written with a WKT literal and not expired after commit
      (``expire_on_commit=False``).

    That last case is not theoretical: it is what order intake produced before
    this was fixed, and mocks never exposed it.
    """
    data = getattr(element, "data", element)

    if isinstance(data, str):
        stripped = data.strip()
        upper = stripped.upper()
        if upper.startswith("SRID=") or upper.startswith("POINT"):
            return _ewkt_to_geo_point(stripped)
        data = bytes.fromhex(stripped)
    elif isinstance(data, memoryview):
        data = bytes(data)

    point = shapely_wkb.loads(bytes(data))
    return GeoPoint(lat=point.y, lng=point.x)

