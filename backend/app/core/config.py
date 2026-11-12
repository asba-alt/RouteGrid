from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root: backend/app/core/config.py -> parents[3]
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    DATABASE_URL: str
    DATABASE_URL_SYNC: str
    REDIS_URL: str = "redis://localhost:6379/0"

    BATCH_SIZE: int = 10
    BATCH_TIMEOUT_SECONDS: int = 15

    # Solver budget for a single batch optimization pass. Local search improves
    # the construction solution by only a fraction of a percent on demo-scale
    # data, so a large budget is wasted wall-clock time.
    OPTIMIZER_TIME_LIMIT_SECONDS: int = 2

    SPEED_FACTOR_KMH: float = 40
    TIME_COMPRESSION_RATIO: int = 60

    WEIGHT_DISTANCE: float = 0.4
    WEIGHT_WORKLOAD: float = 0.3
    WEIGHT_DELIVERY_TIME: float = 0.3

    APP_ENV: str = "development"
    DEBUG: bool = False

    # Comma-separated allowed browser origins. Required in production; local
    # development falls back to the Vite dev server.
    CORS_ORIGINS: str = ""

    # Shared API key required on every request when set. Empty means auth is
    # DISABLED (local development only) — production must set it.
    API_KEY: str = ""

    # Minutes before an inventory hold expires. 0 disables expiry.
    RESERVATION_TTL_MINUTES: int = 0

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() in {"production", "prod"}

    @property
    def cors_origins(self) -> list[str]:
        if self.CORS_ORIGINS.strip():
            return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
        if self.is_production:
            # Fail closed: never fall back to a permissive wildcard in production.
            return []
        return ["http://localhost:5173", "http://127.0.0.1:5173"]

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
