from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def _load_env() -> None:
    here = Path(__file__).resolve()
    for candidate in (
        here.parents[4] / ".env" if len(here.parents) > 4 else None,
        here.parents[2] / ".env",
    ):
        if candidate is not None and candidate.is_file():
            load_dotenv(candidate, override=True)
            return
    load_dotenv(override=True)


_load_env()


class Settings:
    app_name: str = "Interview & Assessment Platform"
    app_version: str = "1.0.0"
    cors_origins: list[str]
    voice_ws_public_url: str
    voice_http_public_url: str
    database_url: str
    redis_url: str
    webhook_secret: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_exp_minutes: int = 720
    admin_username: str
    admin_password: str
    enforce_migrations: bool
    recording_roles: set[str]

    def __init__(self) -> None:
        origins = os.getenv(
            "INTERVIEW_CORS_ORIGINS",
            "http://localhost:8080,http://127.0.0.1:8080,http://localhost:8081,http://127.0.0.1:8081,http://localhost:3000",
        )
        self.cors_origins = [o.strip() for o in origins.split(",") if o.strip()]
        self.voice_ws_public_url = os.getenv("VOICE_WS_PUBLIC_URL", "ws://localhost:8765")
        self.voice_http_public_url = os.getenv("VOICE_HTTP_PUBLIC_URL", "http://localhost:8081")
        self.database_url = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://crm_user:crm_pass@localhost:5432/crm_db",
        )
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.webhook_secret = os.getenv("WEBHOOK_SECRET", "change-this-webhook-secret")
        self.jwt_secret = os.getenv("JWT_SECRET", "change-this-jwt-secret")
        self.jwt_exp_minutes = int(os.getenv("JWT_EXP_MINUTES", "720"))
        self.admin_username = os.getenv("CRM_ADMIN_USERNAME", "admin")
        self.admin_password = os.getenv("CRM_ADMIN_PASSWORD", "admin123")
        self.enforce_migrations = os.getenv("ENFORCE_MIGRATIONS", "false").lower() in {"1", "true", "yes"}
        roles = os.getenv("RECORDING_ACCESS_ROLES", "admin,manager,qa")
        self.recording_roles = {r.strip() for r in roles.split(",") if r.strip()}


settings = Settings()
