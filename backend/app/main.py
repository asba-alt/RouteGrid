from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.disruptions import router as disruption_router
from app.api.routes.health import router as health_router
from app.api.routes.optimization import router as optimization_router
from app.api.routes.orders import router as order_router
from app.api.routes.reservations import router as reservation_router
from app.api.routes.routes import router as routes_router
from app.api.routes.simulation import router as simulation_router
from app.api.routes.vehicles import router as vehicle_router
from app.api.routes.warehouses import router as warehouse_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import RequestContextMiddleware, configure_logging
from app.core.redis import close_redis, init_redis
from app.db.engine import create_engine_from_url
from app.db.session import init_session_factory

configure_logging("DEBUG" if settings.DEBUG else "INFO")


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = create_engine_from_url(settings.DATABASE_URL)
    init_session_factory(engine)
    await init_redis(settings.REDIS_URL)
    try:
        yield
    finally:
        await close_redis()
        await engine.dispose()


app = FastAPI(
    title="RouteGrid",
    version="0.1.0",
    lifespan=lifespan,
    description="Real-time urban logistics optimization and fleet management API.",
)

# Correlation ids + structured access logging.
app.add_middleware(RequestContextMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

register_exception_handlers(app)

app.include_router(health_router)
app.include_router(disruption_router)
app.include_router(warehouse_router)
app.include_router(vehicle_router)
app.include_router(order_router)
app.include_router(reservation_router)
app.include_router(routes_router)
app.include_router(optimization_router)
app.include_router(simulation_router)


@app.get("/", tags=["meta"])
async def root() -> dict:
    return {"message": "RouteGrid API", "docs": "/docs"}
