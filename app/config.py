from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    app_domain: str
    app_email: str
    postgres_db: str
    postgres_user: str
    postgres_password: str
    postgres_host: str
    postgres_port: int
    database_url: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    postgres_db = os.getenv("POSTGRES_DB", "collega")
    postgres_user = os.getenv("POSTGRES_USER", "collega")
    postgres_password = os.getenv("POSTGRES_PASSWORD", "collega")
    postgres_host = os.getenv("POSTGRES_HOST", "postgres")
    postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
    database_url = os.getenv(
        "DATABASE_URL",
        f"postgresql+psycopg://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{postgres_db}",
    )

    return Settings(
        app_domain=os.getenv("APP_DOMAIN", ""),
        app_email=os.getenv("APP_EMAIL", ""),
        postgres_db=postgres_db,
        postgres_user=postgres_user,
        postgres_password=postgres_password,
        postgres_host=postgres_host,
        postgres_port=postgres_port,
        database_url=database_url,
    )
